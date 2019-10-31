from unittest import TestCase
from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.core.crypto.wallet import Wallet
import zmq
import zmq.asyncio
import asyncio


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

