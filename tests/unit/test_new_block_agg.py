from cilantro_ee.nodes.masternode.new_ba import TransactionBatcherInformer, Block, BlockAggregator, BlockAggregatorController
from cilantro_ee.core.sockets.services import _socket
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.core.messages.message import Message, MessageType
from unittest import TestCase
import zmq.asyncio
import asyncio
import secrets
from tests import random_txs

from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.nodes.masternode.block_contender import SubBlockGroup, BlockContender


class TestTransactionBatcherInformer(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()

    def tearDown(self):
        self.ctx.destroy()

    def test_send_ready(self):
        w = Wallet()
        t = TransactionBatcherInformer(socket_id=_socket('tcp://127.0.0.1:8888'), ctx=self.ctx, wallet=w)

        async def recieve():
            s = self.ctx.socket(zmq.PAIR)
            s.connect('tcp://127.0.0.1:8888')
            m = await s.recv()
            return m

        tasks = asyncio.gather(
            recieve(),
            t.send_ready(),
        )

        loop = asyncio.get_event_loop()
        blob, _ = loop.run_until_complete(tasks)

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(blob)

        self.assertEqual(MessageType.READY, msg_type)

    def test_send_hashes_same_list_of_hashes(self):
        w = Wallet()
        t = TransactionBatcherInformer(socket_id=_socket('tcp://127.0.0.1:8888'), ctx=self.ctx, wallet=w)

        async def recieve():
            s = self.ctx.socket(zmq.PAIR)
            s.connect('tcp://127.0.0.1:8888')
            m = await s.recv()
            return m

        tasks = asyncio.gather(
            recieve(),
            t.send_burn_input_hashes([b'a', b'b', b'c', b'd']),
        )

        loop = asyncio.get_event_loop()
        blob, _ = loop.run_until_complete(tasks)

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(blob)

        self.assertEqual(msg_type, MessageType.BURN_INPUT_HASHES)
        self.assertListEqual([i for i in msg.inputHashes], [b'a', b'b', b'c', b'd'])


class TestBlock(TestCase):
    pass


class MockSubscription:
    def __init__(self):
        self.received = []


def random_wallets(n=10):
    return [secrets.token_hex(32) for _ in range(n)]


class TestBlockAggregator(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()

    def tearDown(self):
        self.ctx.destroy()

    def test_block_timeout_without_any_quorum_returns_failed_block(self):
        b = BlockAggregator(subscription=MockSubscription(), block_timeout=1, min_quorum=5, max_quorum=10)

        # Set this true so that it doesn't hang
        b.pending_block.started = True

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        self.assertListEqual(block, [])
        self.assertEqual(kind, 2)

    def test_block_timeout_with_quorum_that_is_90_max_returns_new_block(self):
        b = BlockAggregator(subscription=MockSubscription(), block_timeout=1, min_quorum=10, max_quorum=20)

        b.pending_block.started = True

        wallets = [Wallet() for _ in range(10)]
        print(len(wallets))

        contacts = VKBook(delegates=[w.verifying_key() for w in wallets],
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'\x00' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sbcs = random_txs.x_sbcs_from_tx(input_hash, s.curr_block_hash, wallets=wallets[:-1])

        for i in range(len(wallets)-1):
            b.pending_block.contender.add_sbc(wallets[i].verifying_key(), sbcs[i])

        b.pending_block.contender.get_current_quorum_reached()

        loop = asyncio.get_event_loop()
        block, kind = loop.run_until_complete(b.gather_block())

        print(block, kind)