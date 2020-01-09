from unittest import TestCase
from cilantro_ee.storage.state import MetaDataStorage
import json
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto.transaction import TransactionBuilder
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
import os
import capnp
import secrets
from cilantro_ee.containers.merkle_tree import merklize
from contracting.db import encoder

blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')
subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')
transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')
signal_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/signals.capnp')


class TestStateDriver(TestCase):
    def setUp(self):
        self.r = MetaDataStorage()  # this is a class, not an instance, so we do not instantiate
        self.r.flush()

    def tearDown(self):
        self.r.flush()

    def test_state_updated(self):
        # Generate some random transactions
        transactions = []
        get_sets = []
        for i in range(50):
            w = Wallet()
            tx = TransactionBuilder(w.verifying_key(), contract='currency',
                                    function='transfer',
                                    kwargs={'amount': 10, 'to': 'jeff'},
                                    stamps=500000,
                                    processor=secrets.token_bytes(32),
                                    nonce=i)

            tx.sign(w.signing_key())

            tx.proof = b'\x00'
            tx.proof_generated = True

            packed_tx = transaction_capnp.Transaction.from_bytes_packed(tx.serialize())

            # Create a hashmap between a key and the value it should be set to randomly
            get_set = {secrets.token_hex(8): secrets.token_hex(8)}
            get_sets.append(get_set)

            # Put this hashmap as the state of the contract execution and contruct it into a capnp struct
            tx_data = transaction_capnp.TransactionData.new_message(
                transaction=packed_tx,
                status=0,
                state=json.dumps(get_set),
                stampsUsed=10000
            )

            # Append it to our list
            transactions.append(tx_data)

        # Build a subblock. One will do
        tree = merklize([tx.to_bytes_packed() for tx in transactions])

        w = Wallet()

        sig = w.sign(tree.root)

        sb = subblock_capnp.SubBlock.new_message(
            merkleRoot=tree.root,
            signatures=[sig],
            merkleLeaves=tree.leaves,
            subBlockNum=0,
            inputHash=b'a' * 32,
            transactions=[tx for tx in transactions]
        )

        import hashlib

        h = hashlib.sha3_256()
        h.update(b'\00' * 32)
        h.update(tree.root)

        block = blockdata_capnp.BlockData.new_message(
            blockHash=h.digest(),
            blockNum=1,
            blockOwners=[b'\00' * 32],
            prevBlockHash=b'\00' * 32,
            subBlocks=[sb]
        )

        self.r.update_with_block(block)

        for kv in get_sets:
            k, v = list(kv.items())[0]
            got = self.r.get(k)
            self.assertEqual(v, got)

    # TODO test this with publish transactions

    def test_get_latest_block_hash_with_none_set(self):
        b_hash = self.r.get_latest_block_hash()
        self.assertEqual(b'\x00'*32, b_hash)

    def test_get_latest_block_num_with_none_set(self):
        b_num = self.r.get_latest_block_num()
        self.assertEqual(0, b_num)

    def test_set_get_latest_block_hash(self):
        b_hash = b'A' * 32
        self.r.set_latest_block_hash(b_hash)

        self.assertEqual(self.r.get_latest_block_hash(), b_hash)

    def test_set_get_latest_block_num(self):
        b_num = 9001
        self.r.set_latest_block_num(b_num)

        self.assertEqual(self.r.get_latest_block_num(), b_num)

    def test_set_transaction_data_single_value(self):
        update = {'123': 999}
        encoded = json.dumps(update)
        tx_data = transaction_capnp.TransactionData.new_message(
            state=encoded
        )

        self.r.set_transaction_data(tx=tx_data.to_dict())

        self.assertEqual(self.r.get('123'), 999)

    def test_set_transaction_multiple_values(self):
        update = {'123': 999,
                  'stu': b'555',
                  'something': [1, 2, 3]}

        encoded = encoder.encode(update)
        tx_data = transaction_capnp.TransactionData.new_message(
            state=encoded
        )

        self.r.set_transaction_data(tx=tx_data.to_dict())
        self.assertEqual(self.r.get('123'), 999)
        self.assertEqual(self.r.get('stu'), b'555')
        self.assertEqual(self.r.get('something'), [1, 2, 3])

    def test_set_transaction_corrupted_json_doesnt_work(self):
        update = b'999'
        tx_data = transaction_capnp.TransactionData.new_message(
            state=update
        )
        self.r.set_transaction_data(tx=tx_data.to_dict())

        # Won't write the data because it's not a valid JSON map
        self.assertEqual(len(self.r.keys()), 0)

    def test_set_transaction_non_dicts_dont_work(self):
        update = ['1', 2, 'three']
        encoded = encoder.encode(update)
        tx_data = transaction_capnp.TransactionData.new_message(
            state=encoded
        )
        self.r.set_transaction_data(tx=tx_data.to_dict())

        # Won't write the data because it's not a valid JSON map
        self.assertEqual(len(self.r.keys()), 0)

