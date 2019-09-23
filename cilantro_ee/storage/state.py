from cilantro_ee.logger.base import get_logger
import json
from cilantro_ee.constants import conf
from contracting.db.driver import DatabaseDriver
from contracting.db import encoder

from cilantro_ee.messages import capnp as schemas
import os
import capnp

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')

import contextlib


# Used during catchup to take a block, isolate the nonce_hashes, and calculate what the new nonce should be
# New nonce should be +1 of whatever it was before. This is for when there are multiple transactions in a block
# Or if nonce is none, the first nonce will be 0, so set the current to 1.
def update_nonce_hash(nonce_hash: dict, tx_payload: transaction_capnp.TransactionPayload):
    # Modifies the provided dict
    k = (tx_payload.processor, tx_payload.sender)
    current_nonce = nonce_hash.get(k)

    if current_nonce is None or current_nonce == tx_payload.nonce:
        nonce_hash[k] = tx_payload.nonce + 1


class MetaDataStorage(DatabaseDriver):
    def __init__(self,
                 block_hash_key='_current_block_hash',
                 epoch_hash_key='_current_epoch_hash',
                 block_num_key='_current_block_num',
                 nonce_key='__n',
                 pending_nonce_key='__pn'):

        self.block_hash_key = block_hash_key
        self.epoch_hash_key = epoch_hash_key
        self.block_num_key = block_num_key
        self.log = get_logger('StateDriver')
        self.interface = None

        self.nonce_key = nonce_key
        self.pending_nonce_key = pending_nonce_key

        super().__init__()

    def get(self, key):
        value = super().get(key)
        return encoder.decode(value)

    def set(self, key, value):
        v = encoder.encode(value)
        super().set(key, v)

    def get_latest_block_hash(self):
        block_hash = super().get(self.block_hash_key)
        if block_hash is None:
            return b'\x00' * 32
        return block_hash

    def set_latest_block_hash(self, v: bytes):
        if type(v) == str:
            v = bytes.fromhex(v)
        assert len(v) == 32, 'Hash provided is not 32 bytes.'
        super().set(self.block_hash_key, v)

    latest_block_hash = property(get_latest_block_hash, set_latest_block_hash)

    def get_latest_epoch_hash(self):
        epoch_hash = super().get(self.epoch_hash_key)
        if epoch_hash is None:
            return b'\x00' * 32
        return epoch_hash

    def set_latest_epoch_hash(self, v: bytes):
        if type(v) == str:
            v = bytes.fromhex(v)
        assert len(v) == 32, 'Hash provided is not 32 bytes.'
        super().set(self.epoch_hash_key, v)

    latest_epoch_hash = property(get_latest_epoch_hash, set_latest_epoch_hash)

    def get_latest_block_num(self):
        num = self.get(self.block_num_key)
        if num is None:
            return 0

        return num

    def set_latest_block_num(self, v):
        v = int(v)
        assert v >= 0, 'Block number must be positive integer.'
        self.set(self.block_num_key, v)

    latest_block_num = property(get_latest_block_num, set_latest_block_num)

    def set_transaction_data(self, tx=transaction_capnp.TransactionData):
        if tx.state is not None and len(tx.state) > 0:
            with contextlib.suppress(json.JSONDecodeError):
                sets = json.loads(tx.state)

            if type(sets) != dict:
                return

            # For each KV in the JSON, set the key to the value
            for k, v in sets.items():
                self.set(k, v)

    def commit_nonces(self, nonce_hash=None):
        # Delete pending nonces and update the nonces
        if nonce_hash is not None:
            for k, v in nonce_hash.items():
                processor, sender = k

                self.set_nonce(processor=processor, sender=sender, nonce=v)
                self.delete_pending_nonce(processor=processor, sender=sender)
        else:
            # Commit all pending nonces straight up
            for n in self.iter(self.pending_nonce_key):
                _, processor, sender = n.decode().split(':')

                processor = bytes.fromhex(processor)
                sender = bytes.fromhex(sender)

                nonce = self.get_pending_nonce(processor=processor, sender=sender)

                self.set_nonce(processor=processor, sender=sender, nonce=nonce)
                self.delete(n)

    def delete_pending_nonces(self):
        for nonce in self.iter(self.pending_nonce_key):
            self.delete(nonce)

    def update_with_block(self, block):
        self.log.success('UPDATING STATE')

        # Map of tuple to nonce such that (processor, sender) => nonce
        nonces = {}

        for sb in block.subBlocks:
            for tx in sb.transactions:
                update_nonce_hash(nonce_hash=nonces, tx_payload=tx.transaction.payload)
                self.set_transaction_data(tx=tx)

        self.commit_nonces(nonce_hash=nonces)
        self.delete_pending_nonces()

        # Update our block hash and block num
        self.latest_block_hash = block.blockHash
        self.latest_block_num = block.blockNum

        # Update the epoch hash if it is time
        if block.blockNum % conf.EPOCH_INTERVAL == 0:
            self.latest_epoch_hash = block.blockHash

            # Update rewards

        assert self.latest_block_hash == block.blockHash, \
            "StateUpdate failed! Latest block hash {} does not match block data {}".format(self.latest_block_hash, block)

    @staticmethod
    def n_key(key, processor, sender):
        return ':'.join([key, processor.hex(), sender.hex()])

    # Nonce methods
    def get_pending_nonce(self, processor: bytes, sender: bytes):
        return self.get(self.n_key(self.pending_nonce_key, processor, sender))

    def get_nonce(self, processor: bytes, sender: bytes):
        return self.get(self.n_key(self.nonce_key, processor, sender))

    def set_pending_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.set(self.n_key(self.pending_nonce_key, processor, sender), nonce)

    def set_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.set(self.n_key(self.nonce_key, processor, sender), nonce)

    def delete_pending_nonce(self, processor: bytes, sender: bytes):
        self.delete(self.n_key(self.pending_nonce_key, processor, sender))
