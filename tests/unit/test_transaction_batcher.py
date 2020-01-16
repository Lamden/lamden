from unittest import TestCase
from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.crypto import Wallet
import zmq
import zmq.asyncio
import asyncio

from tests import random_txs

from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.networking.parameters import ServiceType


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestNewTransactionBatcher(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.get_event_loop()

    def tearDown(self):
        self.ctx.destroy()
        #self.loop.close()

    def test_init(self):
        w = Wallet()
        t = TransactionBatcher(socket_base='tcp://127.0.0.1', wallet=w, ctx=self.ctx)

    def test_start_and_stop_works(self):
        w = Wallet()
        t = TransactionBatcher(socket_base='tcp://127.0.0.1', wallet=w, ctx=self.ctx)

        tasks = asyncio.gather(
            t.start(),
            stop_server(t, 0.2)
        )

        self.loop.run_until_complete(tasks)

    def test_input_hash_inbox_burn_input_hashes_removes_batch_ids_from_rate_limiter(self):
        w1 = Wallet()
        t = TransactionBatcher(socket_base='tcp://127.0.0.1', wallet=w1, ctx=self.ctx)

        t.rate_limiter.add_batch_id(b'hello_there')

        self.assertListEqual(t.rate_limiter.sent_batch_ids, [b'hello_there'])

        w2 = Wallet()
        message = Message.get_signed_message_packed_2(wallet=w2,
                                                      msg_type=MessageType.BURN_INPUT_HASHES,
                                                      inputHashes=[b'hello_there'])

        async def get(msg):
            await asyncio.sleep(0.1)
            socket = self.ctx.socket(zmq.PAIR)
            socket.bind('ipc:///tmp/tx_batch_informer')

            await socket.send(msg)

        tasks = asyncio.gather(
            t.start(),
            get(message),
            stop_server(t, 0.2),
        )

        self.loop.run_until_complete(tasks)

        self.assertListEqual(t.rate_limiter.sent_batch_ids, [])

    def test_compose_transactions_publishes_to_subscriber(self):
        w1 = Wallet()
        tx = random_txs.random_packed_tx(0, processor=w1.verifying_key(), give_stamps=True)
        t = TransactionBatcher(socket_base='tcp://127.0.0.1', wallet=w1, ctx=self.ctx)

        t.queue.append((0, tx))
        t.rate_limiter.max_txn_submission_delay = 0

        sub_socket = self.ctx.socket(zmq.SUB)
        sub_sock = t.network_parameters.resolve('tcp://127.0.0.1', ServiceType.TX_BATCHER)
        sub_socket.connect(str(sub_sock))
        sub_socket.setsockopt_string(zmq.SUBSCRIBE, '')

        async def get(socket):
            msg = await socket.recv()
            return msg

        tasks = asyncio.gather(
            t.start(),
            get(sub_socket),
            stop_server(t, 0.3),
        )

        results = self.loop.run_until_complete(tasks)

        msg_type, unpacked, _, _, _ = Message.unpack_message_2(results[1])

        self.assertDictEqual(unpacked.transactions[0].to_dict(), tx.to_dict())
