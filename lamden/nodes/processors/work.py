from lamden.logger.base import get_logger
from lamden.nodes.processors.processor import Processor
from lamden.crypto.wallet import verify
from lamden.crypto.canonical import tx_hash_from_tx
from contracting.db.driver import ContractDriver

class WorkValidator(Processor):
    def __init__(self, hlc_clock, wallet, main_processing_queue, get_last_processed_hlc, stop_node,
                 driver: ContractDriver):

        self.log = get_logger('Work Inbox')

        self.main_processing_queue = main_processing_queue
        self.get_last_processed_hlc = get_last_processed_hlc

        self.driver = driver

        self.wallet = wallet
        self.hlc_clock = hlc_clock
        self.stop_node = stop_node


    async def process_message(self, msg):
        # self.log.debug(msg)
        # self.log.info(f'Received work from {msg["sender"][:8]} {msg["hlc_timestamp"]} {msg["tx"]["metadata"]["signature"][:12] }')

        # NOTE(nikita) make sure message payload is valid BEFORE doing other checks
        if not self.valid_message_payload(msg=msg):
            # TODO I assume just stopping here is good. But what to do from a node audit perspective if nodes are
            # sending bad messages??
            self.log.error('BAD MESSAGE PAYLOAD')
            print('BAD MESSAGE PAYLOAD')
            self.log.debug(msg)
            # self.stop_node()
            # not sure why this would be but it's a check anyway
            return

        if not self.known_masternode(msg=msg):
            self.log.error('Not Known Master')
            print("Not Known Master")
            # TODO Probably should never happen as this filtering should probably be handled at the router level
            return
        
        if not self.valid_signature(message=msg):
            self.log.error(f'Invalid signature received in transaction from master {msg["sender"][:8]}')
            print(f'Invalid signature received in transaction from master {msg["sender"][:8]}')
            return

        if self.older_than_last_processed(msg=msg):
            self.log.error('OLDER HLC RECEIVED')
            # TODO at this point we might be processing a message that is older than one that we already did (from
            # UPDATE Looks like we will catch this situation later.  We can ignore it here
            pass

        self.hlc_clock.merge_hlc_timestamp(event_timestamp=msg['hlc_timestamp'])
        self.main_processing_queue.append(msg)

        # print(f'Received new work from {msg["sender"][:8]} to my queue.')

    def valid_message_payload(self, msg):
        if msg.get("tx", None) is None:
            return False
        if msg.get("hlc_timestamp", None) is None:
            return False
        if msg.get("sender", None) is None:
            return False
        if msg.get("signature", None) is None:
            return False
        return True

    def known_masternode(self, msg):
        masternodes_from_smartcontract = self.driver.driver.get(f'masternodes.S:members') or []

        if msg['sender'] not in masternodes_from_smartcontract and msg['sender'] != self.wallet.verifying_key:
            self.log.error(f'TX Batch received from non-master {msg["sender"][:8]}')
            return False
        else:
            return True

    def valid_signature(self, message):
        tx_hash = tx_hash_from_tx(tx=message['tx'])
        msg = f'{tx_hash}{message["hlc_timestamp"]}'

        try:
            return verify(vk=message['sender'], msg=msg, signature=message['signature'])
        except Exception:
            return False
        return False

    def older_than_last_processed(self, msg):
        tx_age = self.hlc_clock.get_nanos(timestamp=msg['hlc_timestamp'])
        last_hlc = self.get_last_processed_hlc()
        last_processed_age = self.hlc_clock.get_nanos(timestamp=last_hlc)

        if tx_age <= last_processed_age:
            return True
        self.log.error(f'{msg["hlc_timestamp"]} received AFTER {last_hlc} was processed!')
        return False
