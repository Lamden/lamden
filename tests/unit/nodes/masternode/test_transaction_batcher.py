from unittest import TestCase
from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher, NewTransactionBatcher
from cilantro_ee.core.crypto.wallet import Wallet
import zmq
import zmq.asyncio
import asyncio

from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType


class TestTransactionBatcher(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.get_event_loop()

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_init(self):
        w = Wallet()
        TransactionBatcher('127.0.0.1', w.signing_key().hex())

    def test_wait_until_ready_ends_when_ready_is_true(self):
        w = Wallet()
        t = TransactionBatcher('0.0.0.0', w.signing_key().hex())

        async def set_ready():
            t._ready = True

        tasks = asyncio.gather(
            t._wait_until_ready(),
            set_ready()
        )

        t.loop.run_until_complete(tasks)


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestNewTransactionBatcher(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.get_event_loop()

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_init(self):
        w = Wallet()
        t = NewTransactionBatcher(publisher_ip='127.0.0.1', wallet=w, ctx=self.ctx)
        print(t.ipc_id)

    def test_start_and_stop_works(self):
        w = Wallet()
        t = NewTransactionBatcher(publisher_ip='127.0.0.1', wallet=w, ctx=self.ctx)

        tasks = asyncio.gather(
            t.start(),
            stop_server(t, 0.2)
        )

        self.loop.run_until_complete(tasks)

    def test_input_hash_inbox_ready_sets_ready_on_tx_batcher(self):
        w1 = Wallet()
        t = NewTransactionBatcher(publisher_ip='127.0.0.1', wallet=w1, ctx=self.ctx)

        self.assertFalse(t.ready)

        w2 = Wallet()

        message = Message.get_signed_message_packed_2(wallet=w2,
                                                      msg_type=MessageType.READY)

        async def get(msg):
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('ipc:///tmp/masternode-input-hash-inbox')

            await socket.send(msg)

        tasks = asyncio.gather(
            t.input_hash_inbox.serve(),
            get(message),
            stop_server(t.input_hash_inbox, 0.2),
        )

        self.loop.run_until_complete(tasks)

        self.assertTrue(t.ready)

