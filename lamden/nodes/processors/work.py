from lamden.logger.base import get_logger
from lamden.nodes.processors.processor import Processor
from lamden.crypto.wallet import verify
from lamden.crypto.canonical import tx_hash_from_tx
from contracting.db.driver import ContractDriver
from lamden.crypto.transaction import check_nonce
from lamden import storage

BAD_MESSAGE_PAYLOAD = "BAD MESSAGE PAYLOAD"
MASTERNODE_NOT_KNOWN = 'MASTERNODE NOT KNOWN'
OLDER_HLC_RECEIVED = "OLDER HLC RECEIVED"


def valid_message_payload(msg: dict) -> bool:
    if not isinstance(msg, dict):
        return False

    tx = msg.get('tx')
    if not isinstance(tx, dict):
        return False

    payload = tx.get('payload')
    if not isinstance(payload, dict):
        return False

    if not isinstance(payload.get("contract"), str):
        return False
    if not isinstance(payload.get("function"), str):
        return False
    if not isinstance(payload.get("kwargs"), dict):
        return False
    if not isinstance(payload.get("nonce"), int):
        return False
    if not isinstance(payload.get("processor"), str):
        return False
    if not isinstance(payload.get("sender"), str):
        return False
    if not isinstance(payload.get("stamps_supplied"), int):
        return False

    metadata = tx.get('metadata')
    if not isinstance(metadata, dict):
        return False

    if not isinstance(metadata.get("signature"), str):
        return False

    if not isinstance(msg.get("hlc_timestamp"), str):
        return False
    if not isinstance(msg.get("sender"), str):
        return False
    if not isinstance(msg.get("signature"), str):
        return False

    return True

class WorkValidator(Processor):
    def __init__(self, hlc_clock, wallet, main_processing_queue, get_last_processed_hlc, stop_node,
                 driver: ContractDriver, nonces = storage.NonceStorage()):

        self.log = get_logger('Work Inbox')

        self.main_processing_queue = main_processing_queue
        self.get_last_processed_hlc = get_last_processed_hlc

        self.driver = driver
        self.nonces = nonces

        self.wallet = wallet
        self.hlc_clock = hlc_clock
        self.stop_node = stop_node


    async def process_message(self, msg):
        # self.log.debug(msg)
        # self.log.info(f'Received work from {msg["sender"][:8]} {msg["hlc_timestamp"]} {msg["tx"]["metadata"]["signature"][:12] }')

        # NOTE(nikita) make sure message payload is valid BEFORE doing other checks
        if not valid_message_payload(msg=msg):
            # TODO I assume just stopping here is good. But what to do from a node audit perspective if nodes are
            # sending bad messages??
            self.log.error(f' {BAD_MESSAGE_PAYLOAD}')
            print(f'[WORK] {BAD_MESSAGE_PAYLOAD}')
            self.log.debug(f'[WORK] {msg}')
            return

        if not self.known_masternode(msg=msg):
            self.log.error(f' {MASTERNODE_NOT_KNOWN}')
            print(f'[WORK] {MASTERNODE_NOT_KNOWN}')
            # TODO Probably should never happen as this filtering should probably be handled at the router level
            return
        
        if not self.valid_signature(message=msg):
            self.log.error(f'Invalid signature received in transaction from master {msg["sender"][:8]}')
            print(f'[WORK] Invalid signature received in transaction from master {msg["sender"][:8]}')
            #return

        if not self.sent_from_processor(message=msg):
            self.log.error(f'Transaction not sent from processor {msg["sender"][:8]}')
            print(f'[WORK] Invalid signature received in transaction from master {msg["sender"][:8]}')
            #return

        if self.older_than_last_processed(msg=msg):
            self.log.error(f' {OLDER_HLC_RECEIVED}: {msg["hlc_timestamp"]} received AFTER {self.get_last_processed_hlc()} was processed!')
            # TODO at this point we might be processing a message that is older than one that we already did (from
            # UPDATE Looks like we will catch this situation later.  We can ignore it here
            pass

        if not self.check_nonce(msg=msg):
            return

        self.save_nonce(msg=msg)

        self.hlc_clock.merge_hlc_timestamp(event_timestamp=msg['hlc_timestamp'])
        self.main_processing_queue.append(msg)

        # print(f'Received new work from {msg["sender"][:8]} to my queue.')

    def known_masternode(self, msg: dict)  -> bool:
        masternodes_from_smartcontract = self.driver.driver.get(f'masternodes.S:members') or []

        if msg['sender'] not in masternodes_from_smartcontract and msg['sender'] != self.wallet.verifying_key:
            self.log.error(f'TX Batch received from non-master {msg["sender"][:8]}')
            return False
        else:
            return True

    def valid_signature(self, message: dict) -> bool:
        tx_hash = tx_hash_from_tx(tx=message['tx'])
        msg = f'{tx_hash}{message["hlc_timestamp"]}'

        try:
            return verify(vk=message['sender'], msg=msg, signature=message['signature'])
        except Exception:
            return False
        return False

    def sent_from_processor(self, message: dict):
        return message['tx']['payload']['processor'] == message.get('sender')

    def older_than_last_processed(self, msg: dict) -> bool:
        return msg.get('hlc_timestamp') <= self.get_last_processed_hlc()

    def check_nonce(self, msg: dict) -> bool:
        tx = msg.get('tx')
        try:
            valid = check_nonce(tx=tx, nonces=self.nonces)
        except Exception as err:
            valid = False
            self.log.error(err)
            self.log.debug(msg)

        return valid

    def save_nonce(self, msg: dict):
        self.nonces.set_nonce(
            sender=msg['tx']['payload']['sender'],
            processor=msg['tx']['payload']['processor'],
            value=msg['tx']['payload']['nonce']
        )

