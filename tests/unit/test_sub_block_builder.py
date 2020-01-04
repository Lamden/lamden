#
#
from cilantro_ee.crypto import Wallet
from cilantro_ee.core.logger import get_logger
from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.messages.message import Message
from cilantro_ee.messages.capnp_impl.capnp_impl import pack
from cilantro_ee.crypto import TransactionBuilder
#
from cilantro_ee.contracts.sync import extract_vk_args, submit_vkbook
from cilantro_ee.nodes.delegate.sub_block_builder import TransactionBag
from cilantro_ee.nodes.delegate.sub_block_builder import TxnBagManager
#
from unittest import TestCase
from tests.utils.constitution_builder import ConstitutionBuilder

import asyncio
import hashlib
import time
import zmq.asyncio

ctx = zmq.asyncio.Context()
const_builder = ConstitutionBuilder(1, 20, 1, 10, False, False)
book = const_builder.get_constitution()
extract_vk_args(book)
submit_vkbook(book, overwrite=True)

#
_log = get_logger("TestSubBlockBuilder")
#

SK = '11babaea921684a1710cd1f763285af52461d1add0d0caf31cec834ff420d46c'
SK = bytes.fromhex(SK)

w = Wallet(seed=SK)

def get_transaction(amount=10, to='jeff', stamps=500000):
    tx = TransactionBuilder(w.verifying_key(), contract='currency',
                            function='transfer',
                            kwargs={'amount': amount, 'to': to},
                            stamps=stamps, processor=b'', nonce=1)
    tx.sign(w.signing_key())
    packed_tx = tx.serialize()
    return packed_tx
    # mtype, tx, sender, timestamp, is_verified = \
             # Message.unpack_message(pack(int(MessageType.TRANSACTION)), packed_tx)
    # return tx

#
#
class SBBTester:

    @staticmethod
    def get_bag(timestamp, num_txs):
        h = hashlib.sha3_256()
        txns = []
        for idx in range(num_txs):
            tx_bytes = get_transaction()
            h.update(tx_bytes)
            _, tx, _, _, _ = \
                Message.unpack_message(pack(int(MessageType.TRANSACTION)), tx_bytes)

            txns.append(tx)

        h.update('{}'.format(timestamp).encode())
        ih = h.digest()
        _, bag = Message.get_message(MessageType.TRANSACTION_BATCH,
                                     transactions=txns,
                                     timestamp=timestamp,
                                     inputHash=ih)
        return ih, bag


class TestSubBlockBuilder(TestCase):

    def test_transaction_bag(self, *args):
        tb = TransactionBag()
        self.assertTrue(tb.empty_queue())
        timestamp = time.time()
        ih0, bag0 = SBBTester.get_bag(1, 0)
        ih1, bag1 = SBBTester.get_bag(timestamp, 0)
        ih2, bag2 = SBBTester.get_bag(timestamp+2, 5)
        ih3, bag3 = SBBTester.get_bag(timestamp+3, 0)
        ih4, bag4 = SBBTester.get_bag(timestamp+4, 3)
        ih5, bag5 = SBBTester.get_bag(timestamp+5, 0)
        ih6, bag6 = SBBTester.get_bag(timestamp+6, 4)

        ih, bag = tb.get_next_bag()
        self.assertEqual(ih, ih0)
        self.assertTrue(tb.empty_queue())

        tb.add_bag(bag1)
        tb.add_bag(bag0)    # this shouldn't be added as timestamp is lower

        ih, bag = tb.get_next_bag()
        self.assertEqual(ih, ih1)
        self.assertTrue(tb.empty_queue())

        tb.add_bag(bag1)
        self.assertTrue(tb.empty_queue())

        tb.add_bag(bag2)
        tb.add_bag(bag3)
        # removes up to and including ih3 as ih3 is an empty bag
        tb.pop_to_align_bag(ih3)
        self.assertTrue(tb.empty_queue())

        tb.add_bag(bag4)
        tb.add_bag(bag5)
        tb.add_bag(bag6)
        # removes up to ih6, but not ih6 as it is non-empty bag
        tb.pop_to_align_bag(ih6)
        self.assertFalse(tb.empty_queue())

        ih, bag = tb.get_next_bag()
        self.assertEqual(ih, ih6)
        self.assertTrue(tb.empty_queue())

    def run_async_func(self, async_func):
        event_loop = asyncio.new_event_loop()
        event_loop.run_until_complete(async_func)
        event_loop.close()

    def test_txn_bag_manager(self, *args):
        tb = TxnBagManager(3, 1, 1, False)

        self.assertEqual(3, tb.num_txn_bag_queues)

        timestamp = time.time()
        ih1, bag1 = SBBTester.get_bag(timestamp, 0)
        ih2, bag2 = SBBTester.get_bag(timestamp+2, 5)
        ih3, bag3 = SBBTester.get_bag(timestamp+3, 0)
        ih4, bag4 = SBBTester.get_bag(timestamp+4, 3)
        ih5, bag5 = SBBTester.get_bag(timestamp+5, 0)
        ih6, bag6 = SBBTester.get_bag(timestamp+6, 4)

        tb.add_bag(0, bag1)
        self.assertEqual(0, tb.num_non_empty_txn_bags)
        tb.add_bag(1, bag2)
        tb.add_bag(2, bag3)
        tb.add_bag(0, bag4)
        self.assertEqual(2, tb.num_non_empty_txn_bags)
        tb.add_bag(1, bag5)
        self.assertEqual(0, tb.last_active_bag_idx)
        tb.add_bag(1, bag2)
        tb.add_bag(2, bag6)
        self.assertEqual(3, tb.num_non_empty_txn_bags)

        idx = tb.get_active_bag_idx()
        self.run_async_func(tb.get_next_bag())

        idx = tb.get_active_bag_idx()
        self.run_async_func(tb.get_next_bag())

        idx = tb.get_active_bag_idx()
        self.run_async_func(tb.get_next_bag())

        self.assertEqual(3, len(tb.bags_in_process))

        sb_num = [1, 9, 5]
        ihes = [ih1, ih2, ih5]
        tb.align_bags(4, sb_num, ihes)
        self.assertEqual(0, len(tb.bags_in_process))
        self.assertEqual(2, tb.last_active_bag_idx)
        self.assertEqual(2, tb.num_non_empty_txn_bags)

        self.run_async_func(tb.get_next_bag())
        self.assertEqual(0, tb.last_active_bag_idx)
        self.run_async_func(tb.get_next_bag())
        self.assertEqual(2, len(tb.bags_in_process))
        self.assertEqual(2, tb.num_non_empty_txn_bags)
        self.assertEqual(1, tb.last_active_bag_idx)
        tb.remove_top_bag()
        self.assertEqual(2, tb.num_non_empty_txn_bags)
        tb.remove_top_bag()
        self.assertEqual(1, tb.num_non_empty_txn_bags)
        self.assertEqual(1, tb.last_active_bag_idx)




if __name__ == "__main__":
    import unittest
    unittest.main()
