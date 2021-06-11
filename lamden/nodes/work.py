from lamden.logger.base import get_logger
from lamden import router, storage
from lamden.crypto.wallet import verify

class WorkValidator(router.Processor):
    def __init__(self, hlc_clock, wallet, main_processing_queue, get_masters, get_last_processed_hlc, stop_node):

        self.log = get_logger('Work Inbox')

        self.main_processing_queue = main_processing_queue
        self.get_masters = get_masters
        self.get_last_processed_hlc = get_last_processed_hlc

        self.wallet = wallet
        self.hlc_clock = hlc_clock
        self.stop_node = stop_node


    async def process_message(self, msg):
        #self.log.debug(msg)
        # self.log.info(f'Received work from {msg["sender"][:8]} {msg["hlc_timestamp"]} {msg["tx"]["metadata"]["signature"][:12] }')

        #if msg["sender"] == self.wallet.verifying_key:
        #    return


        if msg['tx'] is None:
            self.log.error('TX HAS NO TX INFO!')
            self.log.debug(msg)
            self.stop_node()
            # not sure why this would be but it's a check anyway
            return

        # TODO properly validate this is from a current masternode
        masters = self.get_masters()
        if msg['sender'] not in masters and msg['sender'] != self.wallet.verifying_key:
            self.log.error(f'TX Batch received from non-master {msg["sender"][:8]}')
            return


        if not verify(vk=msg['sender'], msg=msg['input_hash'], signature=msg['signature']):
            self.log.error(f'Invalidly signed TX received from master {msg["sender"][:8]}')

        tx_age = self.hlc_clock.get_nanos(timestamp=msg['hlc_timestamp'])
        last_hlc = self.get_last_processed_hlc()
        last_processed_age = self.hlc_clock.get_nanos(timestamp=last_hlc)

        self.log.debug({
            'message_hlc': {'hlc_timestamp': msg['hlc_timestamp'], 'age': tx_age},
            'last_hlc': {'hlc_timestamp': last_hlc, 'age': last_processed_age}
        })

        if tx_age <= last_processed_age:
            self.log.error(f'{msg["hlc_timestamp"]} received AFTER {last_hlc} was processed!')

        self.hlc_clock.merge_hlc_timestamp(event_timestamp=msg['hlc_timestamp'])
        self.main_processing_queue.append(msg)

        # self.log.info(f'Received new work from {msg["sender"][:8]} to my queue.')
