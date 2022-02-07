from lamden.nodes.masternode import masternode
from lamden.nodes import base
from lamden import router, storage, authentication
from contracting.db.driver import ContractDriver
from contracting.client import ContractingClient
import zmq.asyncio
import asyncio
from lamden.crypto.wallet import Wallet

from unittest import TestCase


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestBlockService(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.authenticator = authentication.SocketAuthenticator(client=ContractingClient(), ctx=self.ctx)

        self.b = masternode.BlockService(
            blocks=storage.BlockStorage(),
            driver=ContractDriver()
        )

        self.r = router.Router(
            socket_id='tcp://127.0.0.1:18001',
            ctx=self.ctx
        )

        self.r.add_service(base.BLOCK_SERVICE, self.b)

    def tearDown(self):
        self.authenticator.authenticator.stop()
        self.ctx.destroy()
        self.loop.close()
        self.b.blocks.drop_collections()
        self.b.driver.flush()

    def test_service_returns_block_height_if_proper_message(self):
        storage.set_latest_block_height(1337, self.b.driver)

        msg = {
            'name': base.GET_HEIGHT,
            'arg': None
        }

        res = self.loop.run_until_complete(self.b.process_message(msg))

        self.assertEqual(res, 1337)

    def test_service_returns_block_for_number_if_exists(self):
        block = {
            'hash': '0' * 64,
            'number': 1337,
            'previous': '0' * 64,
            'subblocks': []
        }

        self.b.blocks.store_block(block)

        msg = {
            'name': base.GET_BLOCK,
            'arg': 1337
        }

        res = self.loop.run_until_complete(self.b.process_message(msg))

        self.assertEqual(res, block)

    def test_service_returns_none_if_bad_message(self):
        msg = {
            'name': base.GET_HEIGHT,
        }

        res = self.loop.run_until_complete(self.b.process_message(msg))

        self.assertIsNone(res)

    def test_service_returns_none_if_blocknum_not_num(self):
        block = {
            'hash': '0' * 64,
            'number': 1337,
            'previous': '0' * 64,
            'subblocks': []
        }

        self.b.blocks.store_block(block)

        msg = {
            'name': base.GET_BLOCK,
            'arg': '1337'
        }

        res = self.loop.run_until_complete(self.b.process_message(msg))

        self.assertIsNone(res)

    def test_service_returns_none_if_no_block_found(self):
        block = {
            'hash': '0' * 64,
            'number': 1337,
            'previous': '0' * 64,
            'subblocks': []
        }

        self.b.blocks.store_block(block)

        msg = {
            'name': base.GET_BLOCK,
            'arg': 7331
        }

        res = self.loop.run_until_complete(self.b.process_message(msg))

        self.assertIsNone(res)

    def test_get_latest_block_height(self):
        storage.set_latest_block_height(1337, self.b.driver)

        vk = Wallet()
        w = Wallet()

        self.authenticator.add_verifying_key(vk.verifying_key)
        self.authenticator.add_verifying_key(w.verifying_key)
        self.authenticator.configure()

        mn_bootnode = 'tcp://127.0.0.1:18001'
        mn_router = router.Router(
            socket_id=mn_bootnode,
            ctx=self.ctx,
            secure=True,
            wallet=vk
        )

        mn_router.add_service(base.BLOCK_SERVICE, self.b)

        async def send_msg():
            res = await base.get_latest_block_height(
                ip=mn_bootnode,
                vk=vk.verifying_key,
                wallet=w,
                ctx=self.ctx
            )
            return res

        tasks = asyncio.gather(
            mn_router.serve(),
            send_msg(),
            stop_server(mn_router, 1)
        )

        _, res, _ = self.loop.run_until_complete(tasks)

        self.assertEqual(res, 1337)

    def test_router_returns_block_for_number_if_exists(self):
        block = {
            'hash': '0' * 64,
            'number': 1337,
            'previous': '0' * 64,
            'subblocks': []
        }

        self.b.blocks.store_block(block)

        vk = Wallet()
        w = Wallet()

        self.authenticator.add_verifying_key(vk.verifying_key)
        self.authenticator.add_verifying_key(w.verifying_key)
        self.authenticator.configure()

        mn_bootnode = 'tcp://127.0.0.1:18001'
        mn_router = router.Router(
            socket_id=mn_bootnode,
            ctx=self.ctx,
            secure=True,
            wallet=vk
        )

        mn_router.add_service(base.BLOCK_SERVICE, self.b)

        async def send_msg():
            res = await base.get_block(
                block_num=1337,
                ip=mn_bootnode,
                vk=vk.verifying_key,
                wallet=w,
                ctx=self.ctx
            )
            return res

        tasks = asyncio.gather(
            mn_router.serve(),
            send_msg(),
            stop_server(mn_router, 1)
        )

        _, res, _ = self.loop.run_until_complete(tasks)

        self.assertEqual(res, block)

    def test_router_returns_none_if_no_block_found(self):
        block = {
            'hash': '0' * 64,
            'number': 1337,
            'previous': '0' * 64,
            'subblocks': []
        }

        self.b.blocks.store_block(block)

        vk = Wallet()
        w = Wallet()

        self.authenticator.add_verifying_key(vk.verifying_key)
        self.authenticator.add_verifying_key(w.verifying_key)
        self.authenticator.configure()

        mn_bootnode = 'tcp://127.0.0.1:18001'
        mn_router = router.Router(
            socket_id=mn_bootnode,
            ctx=self.ctx,
            secure=True,
            wallet=vk
        )

        mn_router.add_service(base.BLOCK_SERVICE, self.b)

        async def send_msg():
            res = await base.get_block(
                block_num=7331,
                ip=mn_bootnode,
                vk=vk.verifying_key,
                wallet=w,
                ctx=self.ctx
            )
            return res

        tasks = asyncio.gather(
            mn_router.serve(),
            send_msg(),
            stop_server(mn_router, 1)
        )

        _, res, _ = self.loop.run_until_complete(tasks)

        self.assertDictEqual(res, router.OK)
