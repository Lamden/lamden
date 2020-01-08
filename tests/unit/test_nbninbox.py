from unittest import TestCase
from cilantro_ee.contracts.sync import extract_vk_args, submit_vkbook
from cilantro_ee.nodes.work_inbox import WorkInbox
from cilantro_ee.nodes.new_block_inbox import NBNInbox, BlockNumberMismatch, NotBlockNotificationMessageType
from tests.utils.constitution_builder import ConstitutionBuilder

from contracting.client import ContractingClient
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.storage.state import MetaDataStorage

from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType

from cilantro_ee.sockets.services import _socket

import zmq.asyncio
import asyncio

# seed the vkbook
def seed_vk_book(num_mn=10, mn_quorum=10, num_del=10, del_quorum=10):
    const_builder = ConstitutionBuilder(num_mn, mn_quorum, num_del,
                                             del_quorum, False, False)
    book = const_builder.get_constitution()
    extract_vk_args(book)
    submit_vkbook(book, overwrite=True)


class TestNBNInbox(TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.ctx = zmq.asyncio.Context()
        seed_vk_book()

    def tearDown(self):
        self.ctx.destroy()
        #self.loop.close()
        ContractingClient().flush()

    def test_init(self):
        n = NBNInbox(contacts=VKBook(), driver=MetaDataStorage(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=self.ctx)

    def test_nbn_puts_messages_on_q(self):
        n = NBNInbox(
            contacts=VKBook(),
            driver=MetaDataStorage(),
            socket_id=_socket('tcp://127.0.0.1:8888'),
            ctx=self.ctx,
            linger=500,
            poll_timeout=500,
            verify=False
        )

        async def send():
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('tcp://127.0.0.1:8888')
            await socket.send(b'')

        async def stop():
            await asyncio.sleep(0.5)
            n.stop()

        tasks = asyncio.gather(
            n.serve(),
            send(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        self.assertEqual(len(n.q), 1)

    def test_nbn_wait_for_next_nbn_returns_first_on_q(self):
        n = NBNInbox(contacts=VKBook(), driver=MetaDataStorage(), socket_id=_socket('tcp://127.0.0.1:8888'),
                     ctx=self.ctx, linger=50, poll_timeout=50, verify=False)

        async def send():
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('tcp://127.0.0.1:8888')
            await socket.send(b'\x00')

        async def stop():
            await asyncio.sleep(0.5)
            n.stop()

        tasks = asyncio.gather(
            n.serve(),
            send(),
            stop(),
            n.wait_for_next_nbn()
        )

        _, _, _, a = self.loop.run_until_complete(tasks)

        self.assertEqual(a, b'\x00')

    def test_block_notification_wrong_type_throws_exception(self):
        n = NBNInbox(contacts=VKBook(), driver=MetaDataStorage(), socket_id=_socket('tcp://127.0.0.1:8888'),
                     ctx=self.ctx, linger=50, poll_timeout=50)

        msg = Message.get_message_packed_2(MessageType.BURN_INPUT_HASHES)
        with self.assertRaises(NotBlockNotificationMessageType):
            n.block_notification_is_valid(msg)

    def test_block_notification_invalid_block_num_throws_exception(self):
        n = NBNInbox(contacts=VKBook(), driver=MetaDataStorage(), socket_id=_socket('tcp://127.0.0.1:8888'),
                     ctx=self.ctx, linger=50, poll_timeout=50)

        n.driver.set_latest_block_num(1)
        msg = Message.get_message_packed_2(MessageType.BLOCK_NOTIFICATION, blockNum=100)

        with self.assertRaises(BlockNumberMismatch):
            n.block_notification_is_valid(msg)


# class TestWorkInbox(TestCase):
#     def setUp(self):
#         self.loop = asyncio.get_event_loop()
#         self.ctx = zmq.asyncio.Context()
#         self.const_builder = ConstitutionBuilder(10, 10, 10, 10, False, False)
#         book = self.const_builder.get_constitution()
#         extract_vk_args(book)
#         submit_vkbook(book, overwrite=True)
#
#     def tearDown(self):
#         self.ctx.destroy()
#         self.loop.stop()
#         ContractingClient().flush()
#
#     def test_init(self):
#         w = WorkInbox(contacts=VKBook(), validity_timeout=1000, socket_id=_socket('tcp://127.0.0.1:8888'),
#                       ctx=self.ctx, linger=50, poll_timeout=50)
#
#         wallets = self.const_builder.get_mn_wallets()
#
#         for wallet in wallets:
#             mtype, msg = Message.get_message_packed(
#                 MessageType.TRANSACTION_BATCH,
#                 transactions=[t for t in tx_list], timestamp=timestamp,
#                 signature=signature, inputHash=inputHash,
#                 sender=self.wallet.verifying_key())
#
#         print(wallets)