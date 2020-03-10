from cilantro_ee.sockets.outbox import Peers, DEL, MN, ALL
from unittest import TestCase
import zmq.asyncio
from cilantro_ee.networking.parameters import Parameters, ServiceType
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.networking.network import Network
from cilantro_ee.sockets.services import SocketStruct
from cilantro_ee.sockets.authentication import SocketAuthenticator

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

    def tearDown(self):
        self.ctx.destroy()

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

