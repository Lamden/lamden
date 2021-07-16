import time
import hashlib

from contracting.stdlib.bridge.time import Datetime
from contracting.db.encoder import encode, safe_repr, convert_dict
from lamden.crypto.canonical import tx_hash_from_tx, format_dictionary, merklize
from lamden.logger.base import get_logger
from lamden.nodes.queue_base import ProcessingQueue
from datetime import datetime



class TxProcessingQueue(ProcessingQueue):
    def __init__(self, client, driver, wallet, hlc_clock, processing_delay, executor,
                 get_current_height, get_current_hash, stop_node, reward_manager):
        super().__init__()

        self.log = get_logger('MAIN PROCESSING QUEUE')

        self.message_received_timestamps = {}

        self.processing_delay = processing_delay

        self.client = client
        self.wallet = wallet
        self.driver = driver
        self.hlc_clock = hlc_clock
        self.executor = executor

        self.get_current_height = get_current_height
        self.get_current_hash = get_current_hash

        self.stop_node = stop_node

        self.reward_manager = reward_manager

        # TODO This is just for testing
        self.total_processed = 0

    def append(self, tx):
        super().append(tx)

        self.message_received_timestamps[tx['hlc_timestamp']] = time.time()
        self.log.debug(f"ADDING {tx['hlc_timestamp']} TO MAIN PROCESSING QUEUE AT {self.message_received_timestamps[tx['hlc_timestamp']]}")

    def flush(self):
        super().flush()
        self.message_received_timestamps = {}

    async def process_next(self):
        # return if the queue is empty
        if len(self.queue) == 0:
            return

        # sort the main processing queue by hlc_timestamp
        self.queue.sort(key=lambda x: x['hlc_timestamp'])

        # Pop it out of the main processing queue
        tx = self.queue.pop(0)

        # get the amount of time the transaction has been in the queue
        time_in_queue = time.time() - self.message_received_timestamps[tx['hlc_timestamp']]

        # get the amount of time this node should holf the transactions
        time_delay = self.hold_time(tx=tx)

        # If the transaction has been held for enough time then process it.
        if time_in_queue > time_delay:
            # clear this hlc_timestamp from the received timestamps memory
            del self.message_received_timestamps[tx['hlc_timestamp']]

            # Process it to get the results
            result = self.process_tx(tx=tx)

            # TODO Remove this as it's for testing
            self.total_processed = self.total_processed + 1

            return {
                'hlc_timestamp': tx['hlc_timestamp'],
                'result': result,
                'transaction_processed': tx
            }
        else:
            # else, put it back in queue
            self.queue.append(tx)
            return None

    def hold_time(self, tx):
        processing_delay = self.processing_delay()

        if tx['sender'] == self.wallet.verifying_key:
            return processing_delay['base'] + processing_delay['self']
        else:
            return processing_delay['base']

    def process_tx(self, tx):
        # Get the environment
        environment = self.get_environment(tx=tx)

        # Execute the transaction
        tx_result = self.execute_tx(
            transaction=tx['tx'],
            stamp_cost=self.client.get_var(contract='stamp_cost', variable='S', arguments=['value']),
            hlc_timestamp=tx['hlc_timestamp'],
            environment=environment
        )

        # Distribute rewards
        self.distribute_rewards(
            tx_result=tx_result,
            contract_name=tx_result['transaction']['payload']['contract']
        )

        # Sign our tx results
        h = hashlib.sha3_256()
        h.update('{}'.format(encode(tx_result).encode()).encode())
        tx_hash = h.hexdigest()

        proof = self.wallet.sign(tx_hash)

        merkle_tree = {
            'leaves': tx_hash,
            'signature': proof
        }

        # Create sub block
        sbc = {
            'input_hash': tx['input_hash'],
            'transactions': [tx_result],
            'merkle_tree': merkle_tree,
            'signer': self.wallet.verifying_key,
            'subblock': 0,
            'previous': self.get_current_hash()
        }

        sbc = format_dictionary(sbc)

        return sbc

    def execute_tx(self, transaction, stamp_cost, hlc_timestamp, environment: dict = {}):
        # Get the currency balance of the tx sender
        balance = self.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[transaction['payload']['sender']],
            mark=False
        )

        print(f'sender_balance_in_execute_tx: {balance}')

        # Execute transaction
        output = self.executor.execute(
            sender=transaction['payload']['sender'],
            contract_name=transaction['payload']['contract'],
            function_name=transaction['payload']['function'],
            stamps=transaction['payload']['stamps_supplied'],
            stamp_cost=stamp_cost,
            kwargs=convert_dict(transaction['payload']['kwargs']),
            environment=environment,
            auto_commit=False
        )

        # Clear pending writes
        self.executor.driver.pending_writes.clear()

        # Log out to the node logs if the tx fails
        if output['status_code'] > 0:
            self.log.error(f'TX executed unsuccessfully. '
                           f'{output["stamps_used"]} stamps used. '
                           f'{len(output["writes"])} writes.'
                           f' Result = {output["result"]}')

        tx_hash = tx_hash_from_tx(transaction)

        # Only apply the writes if the tx passes
        if output['status_code'] == 0:
            writes = [{'key': k, 'value': v} for k, v in output['writes'].items()]
        else:
            # Calculate only stamp deductions
            to_deduct = output['stamps_used'] / stamp_cost
            new_bal = 0
            try:
                new_bal = balance - to_deduct
            except TypeError:
                pass

            writes = [{
                'key': 'currency.balances:{}'.format(transaction['payload']['sender']),
                'value': new_bal
            }]

        tx_output = {
            'hash': tx_hash,
            'transaction': transaction,
            'status': output['status_code'],
            'state': writes,
            'stamps_used': output['stamps_used'],
            'result': safe_repr(output['result']),
            'hlc_timestamp': hlc_timestamp
        }

        tx_output = format_dictionary(tx_output)

        return tx_output

    def distribute_rewards(self, tx_result, contract_name):
        master_reward, delegate_reward, foundation_reward, developer_mapping = \
            self.reward_manager.calculate_tx_output_rewards(tx_result, contract_name, self.client)

        self.reward_manager.distribute_rewards(
            master_reward, delegate_reward, foundation_reward, developer_mapping, self.client
        )

    def get_environment(self, tx):
        now = self.get_now_from_tx(tx=tx)

        return {
            'block_hash': self.get_current_hash(),
            'block_num': self.get_current_height(),
            '__input_hash': tx['input_hash'],  # Used for deterministic entropy for random games
            'now': now,
            'AUXILIARY_SALT': tx['tx']['metadata']['signature']
        }

    def get_now_from_tx(self, tx):
        return Datetime._from_datetime(
            datetime.utcfromtimestamp(tx['tx']['metadata']['timestamp'])
        )