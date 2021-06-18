import time
import json
import hashlib
import asyncio
from contracting.stdlib.bridge.time import Datetime
from contracting.db.encoder import encode, safe_repr, convert_dict
from lamden.crypto.canonical import tx_hash_from_tx, format_dictionary, merklize
from lamden.logger.base import get_logger
from lamden.rewards import RewardManager
from datetime import datetime


class ProcessingQueue:
    def __init__(self, client, driver, wallet, hlc_clock, processing_delay, executor,
                 get_current_height, get_current_hash, stop_node, reward_manager: RewardManager):

        self.log = get_logger('TX PROCESSOR')

        self.running = True
        self.currently_processing = False

        self.main_processing_queue = []
        self.message_received_timestamps = {}
        self.processing_delay_other = processing_delay['base']
        self.processing_delay_self = processing_delay['base'] + processing_delay['self']

        self.client = client
        self.wallet = wallet
        self.driver = driver
        self.hlc_clock = hlc_clock
        self.executor = executor
        self.get_current_height = get_current_height
        self.get_current_hash = get_current_hash
        self.stop_node = stop_node

        self.mock_socket_subscription = []

        self.reward_manager = reward_manager

        # TODO There are just for testing
        self.total_processed = 0

    def start(self):
        self.log.info("STARTING QUEUE")
        self.running = True

    def stop(self):
        self.running = False

    async def stopping(self):
        self.log.info("STOPPING QUEUE")
        while self.currently_processing:
            asyncio.sleep(0)
        self.log.info("STOPPED QUEUE!")

    def append(self, tx):
        self.log.debug(f'adding {tx["hlc_timestamp"]} to queue')
        self.message_received_timestamps[tx['hlc_timestamp']] = time.time()
        self.log.debug(f'adding {tx["hlc_timestamp"]} to queue')
        # self.log.debug(f"ADDING {tx['hlc_timestamp']} TO MAIN PROCESSING QUEUE AT {self.message_received_timestamps[tx['hlc_timestamp']]}")
        self.main_processing_queue.append(tx)

    def hold_time(self, tx):
        if tx['sender'] == self.wallet.verifying_key:
            return self.processing_delay_self
        else:
            return self.processing_delay_other

    async def process_next(self):
        if len(self.main_processing_queue) == 0 or self.currently_processing:
            return
        # run top of stack if it's older than 1 second
        ## self.log.debug('{} waiting items in main queue'.format(len(self.main_processing_queue)))

        self.main_processing_queue.sort(key=lambda x: x['hlc_timestamp'])
        # Pop it out of the main processing queue
        tx = self.main_processing_queue.pop(0)

        if tx['tx'] is None:
            self.log.error('tx has no tx info')
            self.log.debug(tx)
            # self.stop_node()
            # not sure why this would be but it's a check anyway
            return

        # determine its age
        ''' Old time HLC delay checker
        time_in_queue = self.hlc_clock.check_timestamp_age(timestamp=tx['hlc_timestamp'])
        time_in_queue_seconds = time_in_queue / 1000000000
        # self.log.debug("First Item in queue is {} seconds old with an HLC TIMESTAMP of {}".format(time_in_queue_seconds, self.hlc_clock.get_new_hlc_timestamp()))
        '''
        try:
            time_in_queue = time.time() - self.message_received_timestamps[tx['hlc_timestamp']]
            time_delay = self.hold_time(tx)
        except KeyError:
            self.log.debug(self.message_received_timestamps)
            self.log.error(tx['hlc_timestamp'])
            self.stop_node()

        #self.log.debug("First Item in queue is {} seconds old".format(time_in_queue))

        # If the next item in the queue is old enough to process it then go ahead
        if time_in_queue > time_delay:
            self.log.info({
                'queue_length': len(self.main_processing_queue),
                'time_in_queue': time_in_queue,
                'time_delay': time_delay
            })
            # clear this hlc_timestamp from the received timestamps memory
            del self.message_received_timestamps[tx['hlc_timestamp']]

            # Process it to get the results
            result = self.process_tx(tx=tx)

            self.log.debug(json.dumps({
                'type': 'tx_lifecycle',
                'file': 'processing_queue',
                'event': 'processed_from_main_queue',
                'hlc_timestamp': tx['hlc_timestamp'],
                'my_solution': result['merkle_tree']['leaves'][0],
                'system_time': time.time()
            }))

            return {
                'hlc_timestamp': tx['hlc_timestamp'],
                'result': result,
                'transaction_processed': tx
            }
        else:
            #put it back in queue
            self.main_processing_queue.append(tx)
            return None

        # for x in range(len(self.main_processing_queue)):
        #    self.log.info(self.main_processing_queue[x]['hlc_timestamp'])

    def process_tx(self, tx):
        ## self.log.debug("PROCESSING: {}".format(tx['input_hash']))

        # Run mini catch up here to prevent 'desyncing'
        # self.log.info(f'{len(self.new_block_processor.q)} new block(s) to process before execution.')

        try:
            now = Datetime._from_datetime(
                datetime.utcfromtimestamp(tx['tx']['metadata']['timestamp'])
            )
            environment = {
                'block_hash': self.get_current_hash(),
                'block_num': self.get_current_height(),
                '__input_hash': tx['input_hash'],  # Used for deterministic entropy for random games
                'now': now,
            }
        except Exception as err:
            self.log.debug(tx)
            self.log.error(err)

        result = self.execute_tx(
            transaction=tx['tx'],
            stamp_cost=self.client.get_var(contract='stamp_cost', variable='S', arguments=['value']),
            hlc_timestamp=tx['hlc_timestamp'],
            environment=environment
        )

        h = hashlib.sha3_256()
        h.update('{}'.format(encode(result).encode()).encode())
        tx_hash = h.hexdigest()

        proof = self.wallet.sign(tx_hash)

        merkle_tree = {
            'leaves': tx_hash,
            'signature': proof
        }

        sbc = {
            'input_hash': tx['input_hash'],
            'transactions': [result],
            'merkle_tree': merkle_tree,
            'signer': self.wallet.verifying_key,
            'subblock': 0,
            'previous': self.get_current_hash()
        }

        sbc = format_dictionary(sbc)

        # results = self.transaction_executor.execute_work(
        #     driver=self.driver,
        #     work=[tx],
        #     wallet=self.wallet,
        #     previous_block_hash=self.get_current_hash(),
        #     current_height=self.get_current_height(),
        #     stamp_cost=self.client.get_var(contract='stamp_cost', variable='S', arguments=['value'])
        # )

        self.total_processed = self.total_processed + 1
        # self.log.info('{} Processed: {} {}'.format(self.total_processed, tx['hlc_timestamp'], tx['tx']['metadata']['signature'][:12]))
        # self.log.info('{} Left in queue'.format(len(self.main_processing_queue)))

        # self.new_block_processor.clean(self.current_height)
        # self.driver.clear_pending_state()

        return sbc

    def execute_tx(self, transaction, stamp_cost, hlc_timestamp, environment: dict = {}):
        # Deserialize Kwargs. Kwargs should be serialized JSON moving into the future for DX.

        # Add AUXILIARY_SALT for more randomness

        self.log.debug(transaction)

        environment['AUXILIARY_SALT'] = transaction['metadata']['signature']

        balance = self.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[transaction['payload']['sender']],
            mark=False
        )

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

        self.executor.driver.pending_writes.clear()

        if output['status_code'] > 0:
            self.log.error(f'TX executed unsuccessfully. '
                           f'{output["stamps_used"]} stamps used. '
                           f'{len(output["writes"])} writes.'
                           f' Result = {output["result"]}')

        master_reward, delegate_reward, foundation_reward, developer_mapping = \
            self.reward_manager.calculate_tx_output_rewards(output, transaction['payload']['contract'], self.client)

        self.reward_manager.distribute_rewards(
            master_reward, delegate_reward, foundation_reward, developer_mapping, self.client
        )

        # self.log.debug(output['writes'])

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

    def __len__(self):
        return len(self.main_processing_queue)
