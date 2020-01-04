from contracting.db.driver import ContractDriver
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
import os
import capnp

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')
subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')
blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')

PENDING_NONCE_KEY = '__pn'
NONCE_KEY = '__n'


class NonceManager:
    def __init__(self, driver=ContractDriver()):
        self.driver = driver

    @staticmethod
    def update_nonce_hash(nonce_hash: dict, tx_payload):
        if type(tx_payload) != dict:
            tx_payload = tx_payload.to_dict()
        # Modifies the provided dict
        k = (tx_payload['processor'], tx_payload['sender'])
        current_nonce = nonce_hash.get(k)

        if current_nonce is None or current_nonce == tx_payload['nonce']:
            nonce_hash[k] = tx_payload['nonce'] + 1

    @staticmethod
    def n_key(key, processor, sender):
        return ':'.join([key, processor.hex(), sender.hex()])

    # Nonce methods
    def get_pending_nonce(self, processor: bytes, sender: bytes):
        return self.driver.get(self.n_key(PENDING_NONCE_KEY, processor, sender))

    def get_nonce(self, processor: bytes, sender: bytes):
        return self.driver.get(self.n_key(NONCE_KEY, processor, sender))

    def set_pending_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.driver.set(self.n_key(PENDING_NONCE_KEY, processor, sender), nonce)

    def set_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.driver.set(self.n_key(NONCE_KEY, processor, sender), nonce)

    def delete_pending_nonce(self, processor: bytes, sender: bytes):
        self.driver.delete(self.n_key(PENDING_NONCE_KEY, processor, sender))

    def commit_nonces(self, nonce_hash=None):
        # Delete pending nonces and update the nonces
        if nonce_hash is not None:
            for k, v in nonce_hash.items():
                processor, sender = k

                self.set_nonce(processor=processor, sender=sender, nonce=v)
                self.delete_pending_nonce(processor=processor, sender=sender)
        else:
            # Commit all pending nonces straight up
            for n in self.driver.iter(PENDING_NONCE_KEY):
                _, processor, sender = n.split(':')

                processor = bytes.fromhex(processor)
                sender = bytes.fromhex(sender)

                nonce = self.get_pending_nonce(processor=processor, sender=sender)

                self.set_nonce(processor=processor, sender=sender, nonce=nonce)
                self.driver.delete(n)

        self.driver.commit()

    def delete_pending_nonces(self):
        for nonce in self.driver.iter(PENDING_NONCE_KEY):
            self.driver.delete(nonce)

        self.driver.commit()

    def update_nonces_with_block(self, block):
        # Reinitialize the latest nonce. This should probably be abstracted into a seperate class at a later date
        nonces = {}

        for sb in block.subBlocks:
            for tx in sb.transactions:
                self.update_nonce_hash(nonce_hash=nonces, tx_payload=tx.transaction.payload)

        self.commit_nonces(nonce_hash=nonces)
        self.delete_pending_nonces()
