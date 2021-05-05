import time
import hashlib
import asyncio
from lamden.logger.base import get_logger

class TxProcessing:
    def __init__(self, client, driver, wallet, hlc_clock, send_work, processing_delay, transaction_executor,
                 get_current_height, get_current_hash):

        self.log = get_logger('TX PROCESSOR')
        self.main_processing_queue = []
        self.processing_delay = processing_delay

        self.client = client
        self.wallet = wallet
        self.driver = driver
        self.hlc_clock = hlc_clock
        self.send_work = send_work
        self.transaction_executor = transaction_executor
        self.get_current_height = get_current_height
        self.get_current_hash = get_current_hash

        # TODO There are just for testing
        self.total_processed = 0

    async def append(self, tx):
        tx_message = self.make_tx_message(tx)
        await self.send_work(tx_message)
        self.main_processing_queue.append(tx)

    def make_tx_message(self, tx):
        timestamp = int(time.time())

        h = hashlib.sha3_256()
        h.update('{}'.format(timestamp).encode())
        input_hash = h.hexdigest()

        signature = self.wallet.sign(input_hash)

        return {
            'tx': tx,
            'timestamp': timestamp,
            'hlc_timestamp': self.hlc_clock.get_new_hlc_timestamp(),
            'signature': signature,
            'sender': self.wallet.verifying_key,
            'input_hash': input_hash
        }

    def process_next(self):
        # run top of stack if it's older than 1 second
        ## self.log.debug('{} waiting items in main queue'.format(len(self.main_processing_queue)))

        self.main_processing_queue.sort(key=lambda x: x['hlc_timestamp'])
        time_in_queue = self.hlc_clock.check_timestamp_age(timestamp=self.main_processing_queue[0]['hlc_timestamp'])
        time_in_queue_seconds = time_in_queue / 1000000000
        # self.log.debug("First Item in queue is {} seconds old with an HLC TIMESTAMP of {}".format(time_in_queue_seconds, self.hlc_clock.get_new_hlc_timestamp()))

        # If the next item in the queue is old enough to process it then go ahead
        if time_in_queue_seconds > self.processing_delay:
            # Pop it out of the main processing queue
            tx = self.main_processing_queue.pop(0)

            # Process it to get the results
            results = self.process_tx(tx)

            return {
                'tx': tx,
                'results': results
            }

        return None

        # for x in range(len(self.main_processing_queue)):
        #    self.log.info(self.main_processing_queue[x]['hlc_timestamp'])

    def process_tx(self, tx):
        ## self.log.debug("PROCESSING: {}".format(tx['input_hash']))

        # Run mini catch up here to prevent 'desyncing'
        # self.log.info(f'{len(self.new_block_processor.q)} new block(s) to process before execution.')

        results = self.transaction_executor.execute_work(
            driver=self.driver,
            work=[tx],
            wallet=self.wallet,
            previous_block_hash=self.get_current_hash(),
            current_height=self.get_current_height(),
            stamp_cost=self.client.get_var(contract='stamp_cost', variable='S', arguments=['value'])
        )

        # self.log.debug(self.upgrade_manager.node_type)

        self.total_processed = self.total_processed + 1
        self.log.info('{} Processed: {} {}'.format(self.total_processed, tx['hlc_timestamp'], tx['tx']['metadata']['signature'][:12]))

        # self.new_block_processor.clean(self.current_height)
        # self.driver.clear_pending_state()

        return results

    def __len__(self):
        return len(self.main_processing_queue)
