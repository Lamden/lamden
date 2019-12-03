from unittest import TestCase
from cilantro_ee.core.sockets.socket_book import SocketBook
from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.services.overlay.network import Network
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.core.sockets.services import SocketStruct, _socket
from cilantro_ee.contracts import sync

import zmq
import zmq.asyncio

import asyncio


class TestSocketBook(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

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
        m = SocketBook()
        ctx = zmq.Context()
        m.sockets = {'a': ctx.socket(zmq.PUB), 'b': ctx.socket(zmq.PUB)}

        m.remove_node('a')

        self.assertIsNone(m.sockets.get('a'))
        self.assertIsNotNone(m.sockets.get('b'))

    def test_remove_node_doesnt_exist_does_nothing(self):
        m = SocketBook()
        ctx = zmq.Context()
        m.sockets = {'a': ctx.socket(zmq.PUB), 'b': ctx.socket(zmq.PUB)}

        m.remove_node('c')

        self.assertIsNotNone(m.sockets.get('a'))
        self.assertIsNotNone(m.sockets.get('b'))

    def test_refresh(self):
        sync.submit_vkbook(masternodes=['stu', 'raghu'],
                           delegates=['tejas', 'alex', 'steve'],
                           num_boot_mns=2,
                           num_boot_del=3,
                           stamps=True,
                           nonces=True,
                           overwrite=True)

        PhoneBook = VKBook()

        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, ip='127.0.0.1', peer_service_port=10001, event_publisher_port=10002)

        expected = {
            'stu': '127.0.0.1',
            'raghu': '127.0.0.2'
        }
        p1.peer_service.table.peers = expected
        masternodes = SocketBook(network=p1, phonebook_function=PhoneBook.contract.get_masternodes)

        self.assertDictEqual(masternodes.sockets, {})

        loop = asyncio.get_event_loop()
        loop.run_until_complete(masternodes.refresh())

        self.assertDictEqual(masternodes.sockets, expected)

    def test_refresh_remove_old_nodes(self):
        sync.submit_vkbook(masternodes=['stu', 'raghu'],
                           delegates=['tejas', 'alex', 'steve'],
                           num_boot_mns=2,
                           num_boot_del=3,
                           stamps=True,
                           nonces=True,
                           overwrite=True)

        PhoneBook = VKBook()

        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, ip='127.0.0.1', peer_service_port=10001, event_publisher_port=10002)

        ctx = zmq.Context()

        peeps = {
            'stu': ctx.socket(zmq.SUB),
            'raghu': ctx.socket(zmq.SUB),
            'tejas': ctx.socket(zmq.SUB),
            'steve': ctx.socket(zmq.SUB)
        }

        p1.peer_service.table.peers = peeps
        masternodes = SocketBook(network=p1, phonebook_function=PhoneBook.contract.get_masternodes)

        self.assertDictEqual(masternodes.sockets, {})

        loop = asyncio.get_event_loop()
        loop.run_until_complete(masternodes.refresh())

        expected = {
            'stu': peeps['stu'],
            'raghu': peeps['raghu'],
        }

        self.assertDictEqual(masternodes.sockets, expected)

        sync.submit_vkbook(masternodes=['stu', 'raghu'],
                           delegates=['tejas', 'alex', 'steve'],
                           num_boot_mns=2,
                           num_boot_del=3,
                           stamps=True,
                           nonces=True,
                           overwrite=True)

        PhoneBook = VKBook()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(masternodes.refresh())

        expected = {
            'stu': peeps['stu'],
            'tejas': peeps['tejas']
        }

        self.assertDictEqual(masternodes.sockets, expected)
