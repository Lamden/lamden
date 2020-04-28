from cilantro_ee.sockets.outbox import Peers, DEL, MN, ALL
from unittest import TestCase
import zmq.asyncio
from cilantro_ee.networking.parameters import Parameters, ServiceType
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.networking.network import Network
from cilantro_ee.sockets.services import SocketStruct
from cilantro_ee.sockets.authentication import SocketAuthenticator
import asyncio


class MockContacts:
    def __init__(self, masters, delegates):
        self.masternodes = masters
        self.delegates = delegates


class TestPeers(TestCase):
    def setUp(self):
        self.wallet = Wallet()

        # Wallets for VKs
        self.test_wallet_1 = Wallet()
        self.test_wallet_2 = Wallet()

        self.peer_table = {
            self.test_wallet_1.verifying_key().hex(): 'ipc:///tmp/n1',
            self.test_wallet_2.verifying_key().hex(): 'ipc:///tmp/n2',
        }

        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()

        self.contacts = MockContacts(
                masters=[self.test_wallet_1.verifying_key().hex()],
                delegates=[self.test_wallet_2.verifying_key().hex()]
            )

        self.paramaters = Parameters(
            socket_base='tcp://127.0.0.1',
            wallet=self.wallet,
            ctx=self.ctx,
            contacts=self.contacts
        )

        self.authenticator = SocketAuthenticator(wallet=self.wallet, contacts=self.contacts, ctx=self.ctx)

        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def testInit(self):
        p1 = Network(wallet=self.wallet, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        p1.peer_service.table = self.peer_table

        p = Peers(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.paramaters,
            node_type=DEL,
            service_type=ServiceType.INCOMING_WORK
        )

    def test_connect_test_wallet(self):
        p1 = Network(wallet=self.wallet, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        p1.peer_service.table = self.peer_table

        p = Peers(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.paramaters,
            node_type=DEL,
            service_type=ServiceType.INCOMING_WORK
        )

        self.authenticator.sync_certs()

        p.connect(SocketStruct.from_string('ipc:///tmp/n1'), self.test_wallet_1.verifying_key().hex())

        socket = p.sockets.get(self.test_wallet_1.verifying_key().hex())

        self.assertIsNotNone(socket)

    def test_connect_twice_doesnt_modify_socket_object(self):
        p1 = Network(wallet=self.wallet, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        p1.peer_service.table = self.peer_table

        p = Peers(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.paramaters,
            node_type=DEL,
            service_type=ServiceType.INCOMING_WORK
        )

        self.authenticator.sync_certs()

        p.connect(SocketStruct.from_string('ipc:///tmp/n1'), self.test_wallet_1.verifying_key().hex())

        socket = p.sockets.get(self.test_wallet_1.verifying_key().hex())

        self.assertIsNotNone(socket)

        p.connect(SocketStruct.from_string('ipc:///tmp/n1'), self.test_wallet_1.verifying_key().hex())

        socket2 = p.sockets.get(self.test_wallet_1.verifying_key().hex())

        self.assertEqual(socket, socket2)

    def test_sync_adds_two_sockets_from_network_peer_table(self):
        p1 = Network(wallet=self.wallet, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        p1.peer_service.table = self.peer_table

        p = Peers(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.paramaters,
            node_type=ALL,
            service_type=ServiceType.INCOMING_WORK
        )

        self.authenticator.sync_certs()

        async def late_refresh():
            await asyncio.sleep(0.3)
            await self.paramaters.refresh()
            p.sync_sockets()

        async def stop():
            await asyncio.sleep(0.5)
            p1.stop()

        tasks = asyncio.gather(
            p1.start(discover=False),
            late_refresh(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        socket_1 = p.sockets.get(self.test_wallet_1.verifying_key().hex())
        socket_2 = p.sockets.get(self.test_wallet_2.verifying_key().hex())

        self.assertIsNotNone(socket_1)
        self.assertIsNotNone(socket_2)

    def test_sync_adds_del_if_peers_del(self):
        p1 = Network(wallet=self.wallet, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        p1.peer_service.table = self.peer_table

        p = Peers(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.paramaters,
            node_type=DEL,
            service_type=ServiceType.INCOMING_WORK
        )

        self.authenticator.sync_certs()

        async def late_refresh():
            await asyncio.sleep(0.3)
            await self.paramaters.refresh()
            p.sync_sockets()

        async def stop():
            await asyncio.sleep(0.5)
            p1.stop()

        tasks = asyncio.gather(
            p1.start(discover=False),
            late_refresh(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        socket_2 = p.sockets.get(self.test_wallet_2.verifying_key().hex())

        self.assertIsNotNone(socket_2)

    def test_sync_adds_del_if_peers_mn(self):
        p1 = Network(wallet=self.wallet, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        p1.peer_service.table = self.peer_table

        p = Peers(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.paramaters,
            node_type=MN,
            service_type=ServiceType.INCOMING_WORK
        )

        self.authenticator.sync_certs()

        async def late_refresh():
            await asyncio.sleep(0.3)
            await self.paramaters.refresh()
            p.sync_sockets()

        async def stop():
            await asyncio.sleep(0.5)
            p1.stop()

        tasks = asyncio.gather(
            p1.start(discover=False),
            late_refresh(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        socket_1 = p.sockets.get(self.test_wallet_1.verifying_key().hex())

        self.assertIsNotNone(socket_1)

    def test_resync_adds_new_contacts(self):
        p1 = Network(wallet=self.wallet, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        p1.peer_service.table = self.peer_table

        p = Peers(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.paramaters,
            node_type=MN,
            service_type=ServiceType.INCOMING_WORK
        )

        self.authenticator.sync_certs()

        async def late_refresh():
            await asyncio.sleep(0.3)
            await self.paramaters.refresh()
            p.sync_sockets()

        async def stop():
            await asyncio.sleep(0.5)
            p1.stop()

        tasks = asyncio.gather(
            p1.start(discover=False),
            late_refresh(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        socket_1 = p.sockets.get(self.test_wallet_1.verifying_key().hex())

        self.assertIsNotNone(socket_1)

        new_wallet = Wallet()

        p1.peer_service.table[new_wallet.verifying_key().hex()] = 'ipc:///tmp/n3'
        self.contacts.masternodes.append(new_wallet.verifying_key().hex())
        self.authenticator.sync_certs()

        async def late_refresh():
            await asyncio.sleep(0.3)
            await self.paramaters.refresh()
            p.sync_sockets()

        async def stop():
            await asyncio.sleep(0.5)
            p1.stop()

        tasks = asyncio.gather(
            p1.start(discover=False),
            late_refresh(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        socket_1 = p.sockets.get(new_wallet.verifying_key().hex())
        self.assertIsNotNone(socket_1)

    def test_resync_removes_old_contact(self):
        p1 = Network(wallet=self.wallet, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        p1.peer_service.table = self.peer_table

        new_wallet = Wallet()

        p1.peer_service.table[new_wallet.verifying_key().hex()] = 'ipc:///tmp/n3'
        self.contacts.masternodes.append(new_wallet.verifying_key().hex())
        self.authenticator.sync_certs()

        p = Peers(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.paramaters,
            node_type=MN,
            service_type=ServiceType.INCOMING_WORK
        )

        async def late_refresh():
            await asyncio.sleep(0.3)
            await self.paramaters.refresh()
            p.sync_sockets()

        async def stop():
            await asyncio.sleep(0.5)
            p1.stop()

        tasks = asyncio.gather(
            p1.start(discover=False),
            late_refresh(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        socket_1 = p.sockets.get(new_wallet.verifying_key().hex())
        self.assertIsNotNone(socket_1)

        del p1.peer_service.table[new_wallet.verifying_key().hex()]
        self.contacts.masternodes.remove(new_wallet.verifying_key().hex())

        self.authenticator.sync_certs()

        async def late_refresh():
            await asyncio.sleep(0.3)
            await self.paramaters.refresh()
            p.sync_sockets()

        async def stop():
            await asyncio.sleep(0.5)
            p1.stop()

        tasks = asyncio.gather(
            p1.start(discover=False),
            late_refresh(),
            stop()
        )

        self.loop.run_until_complete(tasks)

        socket_1 = p.sockets.get(new_wallet.verifying_key().hex())
        self.assertIsNone(socket_1)
