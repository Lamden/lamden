from unittest import TestCase
from cilantro_ee.sockets.socket_book import SocketBook
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.networking.network import Network
from cilantro_ee.networking.parameters import ServiceType
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.sockets.struct import _socket
from cilantro_ee.contracts import sync
from cilantro_ee.ports import EVENT_PORT
import zmq
import zmq.asyncio
import os
import asyncio


def make_ipc(p):
    try:
        os.mkdir(p)
    except:
        pass


class TestSocketBook(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def get_vkbook_args(self, mns=['stu', 'raghu']):
        args = {}
        args['masternodes'] = mns
        args['masternode_min_quorum'] = 2
        args['delegates'] = ['tejas', 'alex', 'steve']
        args['delegate_min_quorum'] = 2
        args['enable_stamps'] = True
        args['enable_nonces'] = True
        return args

    def test_new_nodes(self):
        current_nodes = {1, 2, 3, 4}
        all_nodes = {1, 2, 3, 4, 5, 6, 7, 8}

        self.assertEqual(SocketBook.new_nodes(all_nodes, current_nodes), {5, 6, 7, 8})

    def test_old_nodes(self):
        current_nodes = {1, 2, 3, 4}
        all_nodes = {1, 2, 3, 4, 5, 6, 7, 8}

        self.assertEqual(SocketBook.old_nodes(all_nodes, current_nodes), set())

    def test_old_nodes_actual_difference(self):
        current_nodes = {1, 2, 3, 4}
        all_nodes = {1, 4, 5, 6, 7, 8}

        self.assertEqual(SocketBook.old_nodes(all_nodes, current_nodes), {2, 3})

    def test_remove_node(self):
        ctx = zmq.Context()
        m = SocketBook(socket_base='tcp://127.0.0.1', ctx=ctx, service_type=ServiceType.BLOCK_NOTIFICATIONS)

        m.sockets = {'a': ctx.socket(zmq.PUB), 'b': ctx.socket(zmq.PUB)}

        m.remove_node('a')

        self.assertIsNone(m.sockets.get('a'))
        self.assertIsNotNone(m.sockets.get('b'))

    def test_remove_node_doesnt_exist_does_nothing(self):
        ctx = zmq.Context()
        m = SocketBook(socket_base='tcp://127.0.0.1', ctx=ctx, service_type=ServiceType.BLOCK_NOTIFICATIONS)
        m.sockets = {'a': ctx.socket(zmq.PUB), 'b': ctx.socket(zmq.PUB)}

        m.remove_node('c')

        self.assertIsNotNone(m.sockets.get('a'))
        self.assertIsNotNone(m.sockets.get('b'))

    def test_refresh(self):
        vkbook_args = self.get_vkbook_args()
        sync.submit_vkbook(vkbook_args, overwrite=True)

        PhoneBook = VKBook()

        w1 = Wallet()

        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        #'tcp://127.0.0.1:10003'

        raw = {
            'stu': 'tcp://127.0.0.1',
            'raghu': 'tcp://127.0.0.2'
        }
        p1.peer_service.table.peers = raw

        expected = {
            'stu': _socket('tcp://127.0.0.1:{}'.format(EVENT_PORT)),
            'raghu': _socket('tcp://127.0.0.2:{}'.format(EVENT_PORT))
        }

        # CHANGE CLIENT TO SOCKET
        masternodes = SocketBook(socket_base='tcp://127.0.0.1',
                                 service_type=ServiceType.EVENT,
                                 ctx=self.ctx,
                                 phonebook_function=PhoneBook.contract.get_masternodes)

        self.assertDictEqual(masternodes.sockets, {})

        async def late_refresh():
            await asyncio.sleep(0.3)
            await masternodes.refresh()

        async def stop():
            await asyncio.sleep(0.5)
            p1.stop()

        tasks = asyncio.gather(
            p1.start(discover=False),
            late_refresh(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        self.assertDictEqual(masternodes.sockets, expected)

    def test_refresh_remove_old_nodes(self):
        vkbook_args = self.get_vkbook_args()
        sync.submit_vkbook(vkbook_args, overwrite=True)

        PhoneBook = VKBook()

        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        peeps = {
            'stu': 'tcp://127.0.0.1',
            'raghu': 'tcp://127.0.0.8',
            'tejas': 'tcp://127.0.2.1',
            'steve': 'tcp://127.0.54.6'
        }

        p1.peer_service.table.peers = peeps

        ctx2 = zmq.asyncio.Context()

        masternodes = SocketBook(socket_base='tcp://127.0.0.1',
                                 service_type=ServiceType.EVENT,
                                 ctx=ctx2,
                                 phonebook_function=PhoneBook.contract.get_masternodes)

        self.assertDictEqual(masternodes.sockets, {})

        async def late_refresh():
            await asyncio.sleep(0.3)
            await masternodes.refresh()

        async def stop():
            await asyncio.sleep(0.5)
            p1.stop()

        tasks = asyncio.gather(
            p1.start(discover=False),
            late_refresh(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        expected = {
            'stu': _socket('tcp://127.0.0.1:{}'.format(EVENT_PORT)),
            'raghu': _socket('tcp://127.0.0.8:{}'.format(EVENT_PORT))
        }

        self.assertDictEqual(masternodes.sockets, expected)

        self.ctx.destroy()
        self.loop.close()

        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        peeps = {
            'stu': 'tcp://127.0.2.1',
            'raghu': 'tcp://127.0.0.8',
            'tejas': 'tcp://127.0.2.1',
            'steve': 'tcp://127.0.54.6'
        }

        p1.peer_service.table.peers = peeps

        vkbook_args = self.get_vkbook_args(mns=['stu', 'tejas'])
        sync.submit_vkbook(vkbook_args, overwrite=True)

        async def late_refresh():
            await asyncio.sleep(0.3)
            await masternodes.refresh()

        async def stop():
            await asyncio.sleep(1)
            p1.stop()

        tasks = asyncio.gather(
            p1.start(discover=False),
            late_refresh(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        expected = {
            'stu': _socket('tcp://127.0.2.1:{}'.format(EVENT_PORT)),
            'tejas': _socket('tcp://127.0.2.1:{}'.format(EVENT_PORT)),
        }

        self.assertDictEqual(masternodes.sockets, expected)
