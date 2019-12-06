# from Deprecated.test import set_testnet_config
# set_testnet_config('vk_dump.json')
#
# from cilantro_ee.constants.system_config import *
from cilantro_ee.utils.hasher import Hasher
#
from contracting.db.cr.callback_data import ExecutionData, SBData
#
# from cilantro_ee.nodes.delegate.block_manager import IPC_IP, IPC_PORT
from cilantro_ee.nodes.delegate.sub_block_builder import TransactionBag
from cilantro_ee.nodes.delegate.sub_block_builder import TxnBagManager
from cilantro_ee.nodes.delegate.sub_block_builder import SubBlockMaker
#
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.capnp_impl.capnp_impl import pack
from cilantro_ee.core.utils.transaction import TransactionBuilder
# from cilantro_ee.nodes.delegate.sub_block_builder import SubBlockBuilder
#
from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock
from cilantro_ee.constants.testnet import *
from cilantro_ee.services.storage.vkbook import PhoneBook
import asyncio
from cilantro_ee.constants.testnet import TESTNET_MASTERNODES
from cilantro_ee.core.crypto import wallet

import hashlib
#
_log = get_logger("TestSubBlockBuilder")
#
TEST_IP = '127.0.0.1'
# DELEGATE_SK = TESTNET_DELEGATES[0]['sk']
DELEGATE_SK = PhoneBook.delegates[0]

IPC_IP = 'block-manager-ipc-sock'
IPC_PORT = 6967
#
# MN_SK1 = TESTNET_MASTERNODES[0]['sk']
# MN_SK2 = TESTNET_MASTERNODES[1]['sk']
MN_SK1 = PhoneBook.masternodes[0]
MN_SK2 = PhoneBook.masternodes[1]
MN_SK1 = TESTNET_MASTERNODES[0]['sk']
MN_SK2 = TESTNET_MASTERNODES[1]['sk']

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
    def test(func):
        @mock.patch("cilantro_ee.core.utils.worker.asyncio")
        @mock.patch("cilantro_ee.core.utils.worker.SocketManager")
        @mock.patch("cilantro_ee.nodes.delegate.block_manager.asyncio")
        @mock.patch("cilantro_ee.nodes.delegate.block_manager.SubBlockBuilder.run")
        def _func(*args, **kwargs):
            return func(*args, **kwargs)
        return _func

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
