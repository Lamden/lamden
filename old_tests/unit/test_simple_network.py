from unittest import TestCase
from lamden.network import *
from lamden.crypto.wallet import Wallet

from contracting.db.encoder import encode, decode
from contracting.client import ContractingClient
from lamden.router import Router

from lamden import authentication

import asyncio
import zmq.asyncio


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestProcessors(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.base_tcp = 'tcp://127.0.0.1:19000'
        self.base_wallet = Wallet()

        self.router = Router(socket_id=self.base_tcp, ctx=self.ctx, wallet=self.base_wallet, secure=True)

        self.authenticator = authentication.SocketAuthenticator(client=ContractingClient(), ctx=self.ctx)
        self.authenticator.add_verifying_key(self.base_wallet.verifying_key)
        self.authenticator.configure()

    def tearDown(self):
        self.authenticator.authenticator.stop()
        self.ctx.destroy()
        self.loop.close()

    def test_identity_processor_create_proof(self):
        w = Wallet()
        i = IdentityProcessor(
            wallet=w,
            pepper='test',
            ip_string='tcp://127.0.0.1:9999'
        )

        proof = i.create_proof()

        self.assertTrue(verify_proof(proof, 'test'))

    def test_identity_false_proof_fails(self):
        w = Wallet()
        i = IdentityProcessor(
            wallet=w,
            pepper='test',
            ip_string='tcp://127.0.0.1:9999'
        )

        proof = i.create_proof()

        proof['signature'] = '0' * 128

        self.assertFalse(verify_proof(proof, 'test'))

    def test_proof_timeout_fails(self):
        w = Wallet()
        i = IdentityProcessor(
            wallet=w,
            pepper='test',
            ip_string='tcp://127.0.0.1:9999'
        )

        proof = i.create_proof()

        proof['timestamp'] = 0

        self.assertFalse(verify_proof(proof, 'test'))

    def test_process_msg_returns_proof_no_matter_what(self):
        w = Wallet()
        i = IdentityProcessor(
            wallet=w,
            pepper='test',
            ip_string='tcp://127.0.0.1:9999'
        )

        loop = asyncio.get_event_loop()
        proof = loop.run_until_complete(i.process_message({}))

        self.assertTrue(verify_proof(proof, 'test'))

    def test_join_processor_returns_none_if_message_not_formatted(self):
        msg = {
            'vk': 'bad',
            'ip': 'bad'
        }

        j = JoinProcessor(
            ctx=self.ctx,
            peers={},
            wallet=Wallet()
        )

        res = self.loop.run_until_complete(j.process_message(msg))

        self.assertIsNone(res)

    # def test_join_processor_good_message_offline_returns_none(self):
    #     w = Wallet()
    #
    #     self.authenticator.add_verifying_key(w.verifying_key)
    #     self.authenticator.configure()
    #
    #     msg = {
    #         'vk': w.verifying_key,
    #         'ip': 'tcp://127.0.0.1:18000'
    #     }
    #
    #     j = JoinProcessor(
    #         ctx=self.ctx,
    #         peers={},
    #         wallet=Wallet()
    #     )
    #
    #     res = self.loop.run_until_complete(j.process_message(msg))
    #     self.assertIsNone(res)

    # def test_join_processor_good_message_bad_proof_returns_none(self):
    #     w = Wallet()
    #
    #     self.authenticator.add_verifying_key(w.verifying_key)
    #     self.authenticator.configure()
    #
    #     msg = {
    #         'vk': w.verifying_key,
    #         'ip': 'tcp://127.0.0.1:18000'
    #     }
    #
    #     j = JoinProcessor(
    #         ctx=self.ctx,
    #         peers={},
    #         wallet=Wallet()
    #     )
    #
    #     async def get():
    #         res = await router.secure_request(
    #             msg={"howdy": 123},
    #             service=JOIN_SERVICE,
    #             wallet=w,
    #             vk=self.base_wallet.verifying_key,
    #             ip=self.base_tcp,
    #             ctx=self.ctx
    #         )
    #
    #         return res
    #
    #     tasks = asyncio.gather(
    #         get(),
    #         j.process_message(msg)
    #     )
    #
    #     res = self.loop.run_until_complete(tasks)
    #
    #     self.assertIsNone(res[1])

    def test_join_processor_good_message_adds_to_peers(self):
        # Create a new peer (router and service)
        peer_to_add = Wallet()
        self.authenticator.add_verifying_key(peer_to_add.verifying_key)
        self.authenticator.configure()

        other_router = Router(
            socket_id='tcp://127.0.0.1:18000',
            ctx=self.ctx,
            wallet=peer_to_add,
            secure=True
        )

        i = IdentityProcessor(
            wallet=peer_to_add,
            pepper='cilantroV1',
            ip_string='tcp://127.0.0.1:18000'
        )

        other_router.add_service(IDENTITY_SERVICE, i)
        ###

        peers = {
            self.base_wallet.verifying_key: 'tcp://127.0.0.1:18001'
        }

        j = JoinProcessor(
            ctx=self.ctx,
            peers=peers,
            wallet=self.base_wallet
        )

        msg = {
            'vk': peer_to_add.verifying_key,
            'ip': 'tcp://127.0.0.1:18000'
        }

        tasks = asyncio.gather(
            other_router.serve(),
            j.process_message(msg),
            stop_server(other_router, 1)
        )

        self.loop.run_until_complete(tasks)

        self.assertEqual(peers[peer_to_add.verifying_key], 'tcp://127.0.0.1:18000')

    def test_join_processor_good_message_forwards_to_peers_and_returns_to_sender(self):
        # JOINER PEER
        peer_to_add = Wallet()
        self.authenticator.add_verifying_key(peer_to_add.verifying_key)
        self.authenticator.configure()

        other_router = Router(
            socket_id='tcp://127.0.0.1:18000',
            ctx=self.ctx,
            wallet=peer_to_add,
            secure=True
        )

        i = IdentityProcessor(
            wallet=peer_to_add,
            pepper='cilantroV1',
            ip_string='tcp://127.0.0.1:18000'
        )

        other_router.add_service(IDENTITY_SERVICE, i)
        ###

        existing_peer = Wallet()
        peers = {
            existing_peer.verifying_key: 'tcp://127.0.0.1:18001'
        }

        # EXISTING PEER
        self.authenticator.add_verifying_key(existing_peer.verifying_key)
        self.authenticator.configure()

        existing_router = Router(
            socket_id='tcp://127.0.0.1:18001',
            ctx=self.ctx,
            wallet=existing_peer,
            secure=True
        )

        i2 = IdentityProcessor(
            wallet=existing_peer,
            pepper='cilantroV1',
            ip_string='tcp://127.0.0.1:18001'
        )

        j2 = JoinProcessor(
            ctx=self.ctx,
            peers=peers,
            wallet=existing_peer
        )

        existing_router.add_service(IDENTITY_SERVICE, i2)
        existing_router.add_service(JOIN_SERVICE, j2)
        ###

        peers_2 = {
            existing_peer.verifying_key: 'tcp://127.0.0.1:18001'
        }
        j = JoinProcessor(
            ctx=self.ctx,
            peers=peers_2,
            wallet=self.base_wallet
        )

        msg = {
            'vk': peer_to_add.verifying_key,
            'ip': 'tcp://127.0.0.1:18000'
        }

        tasks = asyncio.gather(
            other_router.serve(),
            existing_router.serve(),
            j.process_message(msg),
            stop_server(other_router, 1),
            stop_server(existing_router, 1)
        )

        res = self.loop.run_until_complete(tasks)

        # response = decode(res[2])

        expected = {}
        for p in res[2]['peers']:
            expected[p['vk']] = p['ip']

        self.assertDictEqual(peers, expected)
        self.assertDictEqual(peers_2, expected)


class TestNetwork(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.authenticator = authentication.SocketAuthenticator(client=ContractingClient(), ctx=self.ctx)

    def tearDown(self):
        self.authenticator.authenticator.stop()
        self.ctx.destroy()
        self.loop.close()

    def test_start_sends_joins_and_adds_peers_that_respond(self):
        class PeerProcessor1(router.Processor):
            async def process_message(self, msg):
                return peers_1

        class PeerProcessor2(router.Processor):
            async def process_message(self, msg):
                return peers_2

        me = Wallet()

        n_router = router.Router(
                socket_id='tcp://127.0.0.1:18002',
                ctx=self.ctx,
                secure=True,
                wallet=me
            )
        n = Network(
            wallet=me,
            ip_string='tcp://127.0.0.1:18002',
            ctx=self.ctx,
            router=n_router
        )

        bootnodes = [
            'tcp://127.0.0.1:18003',
            'tcp://127.0.0.1:18004'
        ]

        w_1 = Wallet()
        w_2 = Wallet()

        peers_1 = {
            'peers': [{'vk': w_1.verifying_key, 'ip': bootnodes[0]}]
        }
        peers_2 = {
            'peers': [{'vk': w_2.verifying_key, 'ip': bootnodes[1]}]
        }

        router_1 = router.Router(
                socket_id='tcp://127.0.0.1:18003',
                ctx=self.ctx,
                secure=True,
                wallet=w_1
            )
        router_1.add_service('join', PeerProcessor1())

        router_2 = router.Router(
            socket_id='tcp://127.0.0.1:18004',
            ctx=self.ctx,
            secure=True,
            wallet=w_2
        )
        router_2.add_service('join', PeerProcessor2())

        self.authenticator.add_verifying_key(w_1.verifying_key)
        self.authenticator.add_verifying_key(w_2.verifying_key)
        self.authenticator.add_verifying_key(me.verifying_key)
        self.authenticator.configure()

        real_bootnodes = {
            w_1.verifying_key: bootnodes[0],
            w_2.verifying_key: bootnodes[1]
        }

        tasks = asyncio.gather(
            router_1.serve(),
            router_2.serve(),
            n.start(real_bootnodes, [w_1.verifying_key, w_2.verifying_key]),
            stop_server(router_1, 1),
            stop_server(router_2, 1)
        )

        self.loop.run_until_complete(tasks)

        expected = {
            w_1.verifying_key: bootnodes[0],
            w_2.verifying_key: bootnodes[1],
            me.verifying_key: 'tcp://127.0.0.1:18002'
        }

        self.assertDictEqual(n.peers, expected)

    def test_mock_multiple_networks(self):
        w1 = Wallet()
        w2 = Wallet()
        w3 = Wallet()

        ips = ['tcp://127.0.0.1:18001',
               'tcp://127.0.0.1:18002',
               'tcp://127.0.0.1:18003']

        bootnodes = {
            w1.verifying_key: ips[0],
            w2.verifying_key: ips[1],
            w3.verifying_key: ips[2],
        }

        for vk in bootnodes.keys():
            self.authenticator.add_verifying_key(vk)

        self.authenticator.configure()

        r1 = Router(socket_id=ips[0], ctx=self.ctx, wallet=w1, secure=True)
        n1 = Network(wallet=w1, ip_string=ips[0], ctx=self.ctx, router=r1)

        r2 = Router(socket_id=ips[1], ctx=self.ctx, wallet=w2, secure=True)
        n2 = Network(wallet=w2, ip_string=ips[1], ctx=self.ctx, router=r2)

        r3 = Router(socket_id=ips[2], ctx=self.ctx, wallet=w3, secure=True)
        n3 = Network(wallet=w3, ip_string=ips[2], ctx=self.ctx, router=r3)

        vks = [w1.verifying_key,
               w2.verifying_key,
               w3.verifying_key]

        async def stop_server(s: Router, timeout=1):
            await asyncio.sleep(timeout)
            s.stop()

        tasks = asyncio.gather(
            r1.serve(),
            r2.serve(),
            r3.serve(),
            n1.start(bootnodes, vks),
            n2.start(bootnodes, vks),
            n3.start(bootnodes, vks),
            stop_server(r1),
            stop_server(r2),
            stop_server(r3),
        )

        self.loop.run_until_complete(tasks)

        self.assertDictEqual(n1.peers, bootnodes)
        self.assertDictEqual(n2.peers, bootnodes)
        self.assertDictEqual(n3.peers, bootnodes)
