from unittest import TestCase
from cilantro_ee.contracts.sync import extract_vk_args, submit_vkbook
from cilantro_ee.nodes.new_block_inbox import NBNInbox, BlockNumberMismatch, NotBlockNotificationMessageType
from tests.utils.constitution_builder import ConstitutionBuilder

from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.storage.contract import BlockchainDriver
from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType

from cilantro_ee.sockets.services import _socket

from cilantro_ee.crypto.wallet import Wallet
import cilantro_ee
from cilantro_ee.contracts import sync
import zmq.asyncio
import asyncio

# seed the vkbook
def seed_vk_book(num_mn=10, mn_quorum=10, num_del=10, del_quorum=10):
    mn_wallets = [Wallet().verifying_key().hex() for _ in range(num_mn)]
    dn_wallets = [Wallet().verifying_key().hex() for _ in range(num_del)]

    # Sync contracts
    sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json')
    sync.submit_node_election_contracts(
        initial_masternodes=mn_wallets,
        boot_mns=mn_quorum,
        initial_delegates=dn_wallets,
        boot_dels=del_quorum
    )


class TestNBNInbox(TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.ctx = zmq.asyncio.Context()
        seed_vk_book()

    def tearDown(self):
        self.ctx.destroy()
        #self.loop.close()
        BlockchainDriver().flush()

    def test_init(self):
        n = NBNInbox(contacts=VKBook(), driver=BlockchainDriver(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=self.ctx)

    def test_nbn_puts_messages_on_q(self):
        n = NBNInbox(
            contacts=VKBook(),
            driver=BlockchainDriver(),
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
        n = NBNInbox(contacts=VKBook(), driver=BlockchainDriver(), socket_id=_socket('tcp://127.0.0.1:8888'),
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
        n = NBNInbox(contacts=VKBook(), driver=BlockchainDriver(), socket_id=_socket('tcp://127.0.0.1:8888'),
                     ctx=self.ctx, linger=50, poll_timeout=50)

        msg = Message.get_message_packed_2(MessageType.BURN_INPUT_HASHES)
        with self.assertRaises(NotBlockNotificationMessageType):
            n.validate_nbn(msg)

    def test_block_notification_invalid_block_num_throws_exception(self):
        n = NBNInbox(contacts=VKBook(), driver=BlockchainDriver(), socket_id=_socket('tcp://127.0.0.1:8888'),
                     ctx=self.ctx, linger=50, poll_timeout=50)

        n.driver.set_latest_block_num(1)
        msg = Message.get_message_packed_2(MessageType.BLOCK_NOTIFICATION, blockNum=100)

        with self.assertRaises(BlockNumberMismatch):
            n.validate_nbn(msg)


