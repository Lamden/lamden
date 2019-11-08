from cilantro_ee.nodes.masternode.new_ba import TransactionBatcherInformer, Block, BlockAggregator, BlockAggregatorController
from cilantro_ee.core.sockets.services import _socket
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.core.messages.message import Message, MessageType
from unittest import TestCase
import zmq.asyncio
import asyncio


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

        self.assertEqual(w.verifying_key(), sender)
        self.assertTrue(is_verified)
        self.assertEqual(MessageType.READY, msg_type)

    def test_send_hashes_none_does_nothing(self):
        pass

    def test_send_hashes_same_list_of_hashes(self):
        pass
