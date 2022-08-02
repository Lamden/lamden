import time
import datetime
import hashlib
import math

from contracting.stdlib.bridge.time import Datetime
from contracting.db.encoder import encode, safe_repr, convert_dict
from contracting.execution.executor import Executor

from lamden.rewards import RewardManager
from lamden.crypto.canonical import tx_hash_from_tx, hash_from_results, format_dictionary, tx_result_hash_from_tx_result_object
from lamden.logger.base import get_logger
from lamden.nodes.queue_base import ProcessingQueue
from datetime import datetime
from .filequeue import STORAGE_HOME

from threading import Lock

GLOBAL_LOCK = Lock()

class TxProcessingQueue(ProcessingQueue):
    def __init__(self, client, driver, wallet, hlc_clock, processing_delay, stop_node, check_if_already_has_consensus,
                 get_last_hlc_in_consensus, pause_all_queues, unpause_all_queues, reprocess, metering=False, testing=False, debug=False):
        super().__init__()

        self.log = get_logger('MAIN PROCESSING QUEUE')

        self.processing_delay = processing_delay

        self.client = client
        self.wallet = wallet
        self.driver = driver
        self.hlc_clock = hlc_clock
        self.reprocess = reprocess
        self.last_processed_hlc = "0"

        self.get_last_hlc_in_consensus = get_last_hlc_in_consensus
        self.check_if_already_has_consensus = check_if_already_has_consensus
        self.pause_all_queues = pause_all_queues
        self.unpause_all_queues = unpause_all_queues

        self.stop_node = stop_node

        self.reward_manager = RewardManager()
        self.executor = Executor(driver=self.driver, metering=metering)

        self.debug_writes_log = []

        # self.last_time_processed = datetime.datetime.now()

        # TODO This is just for testing
        self.total_processed = 0
        self.testing = testing
        self.debug = debug
        self.detected_rollback = False
        self.append_history = []
        self.currently_processing_hlc = ""

    def append(self, tx):
        if not self.allow_append:
            return

        hlc_timestamp = tx['hlc_timestamp']

        if self.testing:
            self.append_history.append({
                'hlc_timestamp': hlc_timestamp,
                'in_queue': self.hlc_already_in_queue(hlc_timestamp=hlc_timestamp)
            })


        if self.hlc_earlier_than_consensus(hlc_timestamp=hlc_timestamp):
            return

        if not self.hlc_already_in_queue(hlc_timestamp=hlc_timestamp):
            if self.testing:
                tx['in_queue'] = self.hlc_already_in_queue(hlc_timestamp=hlc_timestamp)
                self.append_history.append(tx)

            tx['timestamp'] = time.time()
            super().append(tx)
            self.sort_queue()

    def flush(self):
        super().flush()

    def sort_queue(self):
        # sort the main processing queue by hlc_timestamp
        self.queue.sort(key=lambda x: x['hlc_timestamp'])

    def filter_queue(self):
        # filter the main processing to remove hlc that are already in consensus
        last_hlc_in_consensus = self.get_last_hlc_in_consensus()
        self.queue = [tx for tx in self.queue if tx.get('hlc_timestamp') > last_hlc_in_consensus]

    def hlc_already_in_queue(self, hlc_timestamp):
        for tx in self.queue:
            if tx['hlc_timestamp'] == hlc_timestamp:
                return True
        return False

    def hlc_earlier_than_consensus(self, hlc_timestamp):
        return hlc_timestamp < self.get_last_hlc_in_consensus()

    async def process_next(self):
        #self.log.debug('[START] process_main_queue')

        # filter out all HLCs that are less than our current consensus HLC
        self.filter_queue()

        # return if the queue is empty
        if len(self.queue) == 0:
            #self.log.debug('[STOP] process_main_queue - 1')
            return

        # Pop it out of the main processing queue
        tx = self.queue.pop(0)

        self.currently_processing_hlc = tx['hlc_timestamp']

        # get the amount of time the transaction has been in the queue
        time_in_queue = time.time() - tx.get('timestamp')

        # get the amount of time this node should hold the transactions
        time_delay = self.hold_time(tx=tx)

        # If the transaction has been held for enough time then process it.
        if time_in_queue > time_delay:
            '''
            if self.debug:
                self.log.debug(json.dumps({
                    'type': 'tx_lifecycle',
                    'file': 'processing_queue',
                    'event': 'currently_processing_hlc',
                    'hlc_timestamp': self.currently_processing_hlc,
                    'system_time': time.time()
                }))
            '''

            if self.currently_processing_hlc < self.last_processed_hlc:
                self.log.error(f"ROLLING BACK to {self.currently_processing_hlc}")
                await self.node_rollback(tx=tx)
            else:
                # Process it to get the results
                try:
                    del tx['timestamp']
                    processing_results = self.process_tx(tx=tx)

                except Exception as err:
                    self.log.error(err)
                    print(err)
                    # self.log.debug('[STOP] process_main_queue - 2')
                    return

                # TODO Remove this as it's for testing
                self.total_processed = self.total_processed + 1
                self.last_processed_hlc = self.currently_processing_hlc
                self.currently_processing_hlc = ""

                # self.log.debug('[STOP] process_main_queue - 3')
                return processing_results
        else:
            # else, put it back in queue
            self.queue.insert(0, tx)
            # self.log.debug('[STOP] process_main_queue - 4')
            return None

    def hold_time(self, tx):
        processing_delay = self.processing_delay()

        if tx.get('sender') == self.wallet.verifying_key:
            return processing_delay['base'] + processing_delay['self']
        else:
            return processing_delay['base']

    def process_tx(self, tx):
        # TODO better error handling of anything in here
        # Get the environment
        environment = self.get_environment(tx=tx)
        transaction = tx['tx']
        stamp_cost = self.client.get_var(contract='stamp_cost', variable='S', arguments=['value']) or 1
        hlc_timestamp = tx['hlc_timestamp']

        # Execute the transaction
        GLOBAL_LOCK.acquire()
        output = self.execute_tx(
            transaction=transaction,
            stamp_cost=stamp_cost,
            environment=environment
        )
        GLOBAL_LOCK.release()

        if len(output['writes']) == 0:
            self.log.error("TX HAD NO WRITES!")

        # Process the result of the executor
        tx_result = self.process_tx_output(
            output=output,
            transaction=transaction,
            stamp_cost=stamp_cost
        )

        # self.driver.soft_apply(hcl=hlc_timestamp)

        # Distribute rewards
        rewards = self.distribute_rewards(
            total_stamps_to_split=output['stamps_used'],
            contract_name=tx_result['transaction']['payload']['contract']
        )

        # self.driver.soft_apply_rewards(hcl=hlc_timestamp)

        # Create merkle
        sign_info = self.sign_tx_results(tx_result=tx_result, hlc_timestamp=hlc_timestamp, rewards=rewards)

        # Return a sub block
        return {
            'tx_result': tx_result,
            'proof': sign_info,
            'hlc_timestamp': hlc_timestamp,
            'rewards': rewards,
            'tx_message': {
                'signature': tx['signature'],
                'sender': tx['sender']
            }
        }

    def execute_tx(self, transaction, stamp_cost, environment: dict = {}):
        # TODO better error handling of anything in here

        try:
            # Execute transaction
            return self.executor.execute(
                sender=transaction['payload']['sender'],
                contract_name=transaction['payload']['contract'],
                function_name=transaction['payload']['function'],
                stamps=transaction['payload']['stamps_supplied'],
                stamp_cost=stamp_cost,
                kwargs=convert_dict(transaction['payload']['kwargs']),
                environment=environment,
                auto_commit=False
            )
        except TypeError as err:
            self.log.error(err)
            self.log.debug({
                'transaction': transaction,
                'sender': transaction['payload']['sender'],
                'contract_name': transaction['payload']['contract'],
                'function_name': transaction['payload']['function'],
                'stamps': transaction['payload']['stamps_supplied'],
                'stamp_cost': stamp_cost,
                'kwargs': convert_dict(transaction['payload']['kwargs']),
                'environment': environment,
                'auto_commit': False
            })
            self.stop_node()

    def process_tx_output(self, output, transaction, stamp_cost):
        # Clear pending writes, stu said to comment this out
        # self.executor.driver.pending_writes.clear()

        # Log out to the node logs if the tx fails
        if output['status_code'] > 0:
            self.log.error(f'TX executed unsuccessfully. '
                           f'{output["stamps_used"]} stamps used. '
                           f'{len(output["writes"])} writes.'
                           f' Result = {output["result"]}')

        tx_hash = tx_hash_from_tx(transaction)

        writes = self.determine_writes_from_output(
            status_code=output['status_code'],
            ouput_writes=output['writes'],
            stamps_used=output['stamps_used'],
            stamp_cost=stamp_cost,
            tx_sender=transaction['payload']['sender']
        )

        tx_output = {
            'hash': tx_hash,
            'transaction': transaction,
            'status': output['status_code'],
            'state': writes,
            'stamps_used': output['stamps_used'],
            'result': safe_repr(output['result'])
        }

        tx_output = format_dictionary(tx_output)

        return tx_output

    def determine_writes_from_output(self, status_code, ouput_writes, stamps_used, stamp_cost, tx_sender):
        # Only apply the writes if the tx passes
        if status_code == 0:
            writes = [{'key': k, 'value': v} for k, v in ouput_writes.items()]
        else:
            sender_balance = self.executor.driver.get_var(
                contract='currency',
                variable='balances',
                arguments=[tx_sender],
                mark=False
            )

            # Calculate only stamp deductions
            to_deduct = stamps_used / stamp_cost
            new_bal = 0
            try:
                new_bal = sender_balance - to_deduct
            except TypeError:
                pass

            writes = [{
                'key': 'currency.balances:{}'.format(tx_sender),
                'value': new_bal
            }]

        return writes

    def distribute_rewards(self, total_stamps_to_split, contract_name: str) -> dict:

        master_reward, delegate_reward, foundation_reward, developer_mapping = \
            self.reward_manager.calculate_tx_output_rewards(
                total_stamps_to_split=total_stamps_to_split,
                contract=contract_name,
                client=self.client
            )

        return self.reward_manager.distribute_rewards(
            master_reward, delegate_reward, foundation_reward, developer_mapping, self.client
        )

    def sign_tx_results(self, tx_result, hlc_timestamp, rewards):
        tx_result_hash = tx_result_hash_from_tx_result_object(
            tx_result=tx_result,
            hlc_timestamp=hlc_timestamp,
            rewards=rewards
        )

        signature = self.wallet.sign(tx_result_hash)

        return {
            'signature': signature,
            'signer': self.wallet.verifying_key
        }

    def get_environment(self, tx):
        nanos = self.get_nanos_from_tx(tx=tx)

        return {
            'block_hash': self.get_nanos_hash(nanos=nanos),  # hash nanos
            'block_num': nanos,  # hlc to nanos
            '__input_hash': self.get_hlc_hash_from_tx(tx=tx),  # Used for deterministic entropy for random games
            'now': self.get_now_from_nanos(nanos=nanos),
            'AUXILIARY_SALT': tx['signature']
        }

    def get_hlc_hash_from_tx(self, tx):
        h = hashlib.sha3_256()
        h.update('{}'.format(tx['hlc_timestamp']).encode())
        return h.hexdigest()

    def get_nanos_hash(self, nanos):
        h = hashlib.sha3_256()
        h.update('{}'.format(nanos).encode())
        return h.hexdigest()

    def get_nanos_from_tx(self, tx):
        return self.hlc_clock.get_nanos(timestamp=tx['hlc_timestamp'])

    def get_now_from_nanos(self, nanos):
        return Datetime._from_datetime(
            datetime.utcfromtimestamp(math.ceil(nanos / 1e9))
        )

    async def node_rollback(self, tx):
        start_time = time.time()
        try:
            self.log.info('pause_all_queues')
            await self.pause_all_queues()
            self.log.info('reprocess')
            await self.reprocess(tx=tx)
            self.log.info(f'Reprocessing took { time.time() - start_time} seconds.')
            self.log.info('unpause_all_queues')
            self.unpause_all_queues()
        except Exception as err:
            self.log.info('node_rollback ERROR')
            self.log.error(err)
