import unittest
from unittest import TestCase
import zmq, zmq.asyncio, asyncio
from zmq.auth.thread import ThreadAuthenticator
from zmq.auth.asyncio import AsyncioAuthenticator
from cilantro.protocol.overlay.ironhouse import Ironhouse
from zmq.utils.z85 import decode, encode
from os import listdir, makedirs
from os.path import exists
from threading import Timer
import asyncio, shutil
from cilantro.utils.test.overlay import *

def auth_validate(vk):
    print('Test: Received on validation: {}'.format(vk))
    return True

class TestIronhouseBase(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.sk = '06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a'
        self.vk = '82540bb5a9c84162214c5540d6e43be49bbfe19cf49685660cab608998a65144'
        self.private_key = 'f0ca3d349e56e419e72f11c1fd734ae929a483f9490907d2ded554d9f794f361'
        self.public_key = '73619fa1464ce16802b480a0fd7868ffcce0f7285050a927a07ef1ffdd34c162'
        self.curve_public_key = b'B77YmmOI=O0<)GJ@DJ2Q+&5jzp/absPNMCh?88@S'
        self.ironhouse = Ironhouse(self.sk, wipe_certs=True, auth_validate=auth_validate)
        self.secret = self.ironhouse.secret

class TestConsts(TestIronhouseBase):
    def test_assert_paths(self):
        self.assertEqual(self.ironhouse.base_dir, 'certs/{}'.format(self.ironhouse.keyname), 'key folder is incorrect')
        self.assertEqual(self.ironhouse.authorized_keys_dir, 'certs/{}/authorized_keys'.format(self.ironhouse.keyname), 'public dir is incorrect')

    def test_generate_certificates_failed(self):
        self.ironhouse.wipe_certs = False
        shutil.rmtree(self.ironhouse.base_dir)
        self.ironhouse.generate_certificates(self.sk, wipe_certs=True)
        self.assertTrue(listdir(self.ironhouse.authorized_keys_dir) == ['{}.key'.format(self.ironhouse.keyname)], 'public keys dir should not be created')

    def test_generate_certificates(self):
        self.ironhouse.generate_certificates(self.sk, wipe_certs=True)
        self.assertTrue(listdir(self.ironhouse.authorized_keys_dir), 'public keys dir not created')
        self.assertEqual(self.private_key, decode(self.ironhouse.secret).hex(), 'secret key generation is incorrect')
        self.assertEqual(self.public_key, decode(self.ironhouse.public_key).hex(), 'public key generation is incorrect')

    def test_vk2pk(self):
        self.assertEqual(decode(self.ironhouse.vk2pk(self.vk)).hex(), self.public_key, 'conversion of vk to pk failed')

    def test_generate_from_private_key(self):
        makedirs(self.ironhouse.keys_dir, exist_ok=True)
        self.ironhouse.create_from_private_key(self.private_key)
        self.assertTrue(listdir(self.ironhouse.authorized_keys_dir), 'public keys dir not created')
        self.assertEqual(self.private_key, decode(self.ironhouse.secret).hex(), 'secret key generation is incorrect')
        self.assertEqual(self.public_key, decode(self.ironhouse.public_key).hex(), 'public key generation is incorrect')

    def test_generate_from_public_key(self):
        self.ironhouse.daemon_context, self.ironhouse.daemon_auth = self.ironhouse.secure_context(async=True)
        self.ironhouse.add_public_key(encode(self.public_key.encode()))
        self.assertTrue(listdir(self.ironhouse.authorized_keys_dir), 'public keys dir not created')
        self.assertTrue(exists('{}/{}.key'.format(self.ironhouse.authorized_keys_dir, self.ironhouse.keyname)), 'public key not generated')
        self.ironhouse.daemon_auth.stop()

class TestAuthSync(TestIronhouseBase):

    def test_secure_context_sync(self):
        ctx, auth = self.ironhouse.secure_context(async=False)
        self.assertIsInstance(ctx, zmq.Context, 'synchronous context created incorrectly')
        self.assertIsInstance(auth, ThreadAuthenticator, 'synchronous auth object created incorrectly')
        auth.stop()

    def test_secure_socket_sync(self):
        ctx, auth = self.ironhouse.secure_context(async=False)
        sock = ctx.socket(zmq.REP)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure REP socket')

        sock = ctx.socket(zmq.REQ)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure REQ socket')

        sock = ctx.socket(zmq.PUSH)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure PUSH socket')

        sock = ctx.socket(zmq.PULL)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure PULL socket')

        sock = ctx.socket(zmq.DEALER)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure DEALER socket')

        sock = ctx.socket(zmq.ROUTER)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure ROUTER socket')

        sock = ctx.socket(zmq.PUB)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure PUB socket')

        sock = ctx.socket(zmq.SUB)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure SUB socket')
        sec_sock.close()

        auth.stop()

class TestAuthAsync(TestIronhouseBase):

    def test_secure_context_async(self):
        ctx, auth = self.ironhouse.secure_context(async=True)
        self.assertIsInstance(ctx, zmq.asyncio.Context, 'asynchronous context created incorrectly')
        self.assertIsInstance(auth, AsyncioAuthenticator, 'synchronous auth object created incorrectly')
        if not auth._AsyncioAuthenticator__task.done():
            auth.stop()

    def test_secure_socket_async(self):
        ctx, auth = self.ironhouse.secure_context(async=True)
        sock = ctx.socket(zmq.REP)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure REP socket')

        sock = ctx.socket(zmq.REQ)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure REQ socket')

        sock = ctx.socket(zmq.PUSH)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure PUSH socket')

        sock = ctx.socket(zmq.PULL)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure PULL socket')

        sock = ctx.socket(zmq.DEALER)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure DEALER socket')

        sock = ctx.socket(zmq.ROUTER)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure ROUTER socket')

        sock = ctx.socket(zmq.PUB)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure PUB socket')

        sock = ctx.socket(zmq.SUB)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure SUB socket')

        sec_sock.close()
        if not auth._AsyncioAuthenticator__task.done():
            auth.stop()

    def test_reconfigure_curve(self):
        ctx, auth = self.ironhouse.secure_context(async=True)
        sock = ctx.socket(zmq.REP)
        sec_sock = self.ironhouse.secure_socket(sock, self.secret, self.curve_public_key)
        auth.configure_curve(domain='*', location=self.ironhouse.authorized_keys_dir)
        self.assertIn(self.curve_public_key, auth.certs['*'].keys(), 'cannot find cert in auth')
        sec_sock.close()
        if not auth._AsyncioAuthenticator__task.done():
            auth.stop()

class TestServer(TestIronhouseBase):
    def test_secure_server(self):
        ip = '127.0.0.1'
        port = 4523
        async def send_async_sec():
            client = self.ironhouse.ctx.socket(zmq.REQ)
            client = self.ironhouse.secure_socket(client, self.secret, self.curve_public_key, self.curve_public_key)
            client.connect('tcp://{}:{}'.format(ip, port))
            client.send(self.vk.encode())
            client.close()
            self.ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)


        self.ironhouse.setup_secure_server()
        self.assertIsInstance(self.ironhouse.ctx, zmq.Context, 'asynchronous context created incorrectly')
        self.assertIsInstance(self.ironhouse.sec_sock, zmq.sugar.socket.Socket, 'unable to secure a socket')

        self.loop.run_until_complete(
            asyncio.ensure_future(send_async_sec())
        )

    def test_authenticate(self):
        port = 5523
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(self.fake['curve_key'], '127.0.0.1', port)
            self.assertTrue(authorized)
            self.ironhouse.cleanup()
            self.fake_ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.fake = genkeys('91f7021a9e8c65ca873747ae24de08e0a7acf58159a8aa6548910fe152dab3d8')
        self.fake_ironhouse = Ironhouse(self.fake['sk'], wipe_certs=True, auth_validate=auth_validate, auth_port=port, keyname='fake')
        self.fake_ironhouse.setup_secure_server()
        self.fake_ironhouse.add_public_key(self.curve_public_key)
        self.ironhouse.setup_secure_server()
        self.ironhouse.add_public_key(self.fake['curve_key'])

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_authenticate_self(self):
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(self.curve_public_key, '127.0.0.1')
            self.assertTrue(authorized)
            self.ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.ironhouse.setup_secure_server()

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_authenticate_then_reject(self):
        port = 5523
        async def send_async_sec():
            await self.ironhouse.authenticate(self.fake['curve_key'], '127.0.0.1', port)
            self.ironhouse.remove_public_key(self.fake['curve_key'])
            self.assertFalse(self.ironhouse.authorized_keys[self.fake['curve_key']])
            self.ironhouse.cleanup()
            self.fake_ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.fake = genkeys('91f7021a9e8c65ca873747ae24de08e0a7acf58159a8aa6548910fe152dab3d8')
        self.fake_ironhouse = Ironhouse(self.fake['sk'], wipe_certs=True, auth_validate=auth_validate, auth_port=port, keyname='fake')
        self.fake_ironhouse.setup_secure_server()
        self.fake_ironhouse.add_public_key(self.curve_public_key)
        self.ironhouse.setup_secure_server()
        self.ironhouse.add_public_key(self.fake['curve_key'])

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_authenticate_fail(self):
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(b'A/c=Kn2)aHRI*>fK-{v*r^YCyXJ//3.CGQQC@A9J', '127.0.0.1')
            self.assertEqual(authorized, 'no_reply')
            self.ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.ironhouse.setup_secure_server()

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_auth_validate(self):
        port = 5523
        self.validated = False
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(self.fake['curve_key'], '127.0.0.1', port)
            self.assertTrue(self.ironhouse.authorized_keys[self.fake['curve_key']])
            self.assertTrue(authorized)
            self.assertTrue(self.validated)
            self.ironhouse.cleanup()
            self.fake_ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        def auth_validate_fake(vk):
            self.validated = True
            return True

        def auth_validate(vk):
            return vk == 'b9284b28589523f055ae5b54c98b0b904a1df3b0be5d546d30208d0516e71aa0'

        self.fake = genkeys('7ae3fcfd3a9047adbec6ad11e5a58036df9934dc0746431d80b49d25584d7e78')
        self.fake_ironhouse = Ironhouse(self.fake['sk'], wipe_certs=True, auth_validate=auth_validate, auth_port=port, keyname='fake')
        self.fake_ironhouse.setup_secure_server()
        self.fake_ironhouse.add_public_key(self.curve_public_key)
        self.fake_ironhouse.auth_validate = auth_validate_fake
        self.ironhouse.setup_secure_server()
        self.ironhouse.add_public_key(self.fake['curve_key'])
        self.ironhouse.auth_validate = auth_validate

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_auth_validate_default(self):
        port = 5523
        async def send_async_sec():
            authorized = await self.dih.authenticate(self.a['curve_key'], '127.0.0.1', port)
            self.assertTrue(authorized)
            self.aih.cleanup()
            self.dih.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.a = genkeys('5664ec7306cc22e56820ae988b983bdc8ebec8246cdd771cfee9671299e98e3c')
        self.aih = Ironhouse(self.a['sk'], wipe_certs=True, auth_port=port, keyname='a')
        self.aih.setup_secure_server()
        self.aih.add_public_key(self.curve_public_key)

        self.dih = Ironhouse(self.sk, wipe_certs=True)
        self.dih.setup_secure_server()
        self.dih.add_public_key(self.a['curve_key'])

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_auth_invalid_public_key(self):
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(b'ack', '127.0.0.1', 1234)
            self.assertEqual(authorized, 'invalid')
            self.ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.ironhouse.setup_secure_server()

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_auth_validate_fail_validate(self):
        port = 5523
        self.validated = False
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(self.fake['curve_key'], '127.0.0.1', port)
            self.assertEqual(authorized, 'unauthorized')
            self.assertTrue(self.validated)
            self.ironhouse.cleanup()
            self.fake_ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        def auth_validate_fake(vk):
            self.validated = True
            return True

        def auth_validate(vk):
            return vk == b'catastrophe'

        self.fake = genkeys('7ae3fcfd3a9047adbec6ad11e5a58036df9934dc0746431d80b49d25584d7e78')
        self.fake_ironhouse = Ironhouse(self.fake['sk'], wipe_certs=True, auth_validate=auth_validate, auth_port=port, keyname='fake')
        self.fake_ironhouse.setup_secure_server()
        self.fake_ironhouse.add_public_key(self.curve_public_key)
        self.fake_ironhouse.auth_validate = auth_validate_fake
        self.ironhouse.setup_secure_server()
        self.ironhouse.add_public_key(self.fake['curve_key'])
        self.ironhouse.auth_validate = auth_validate

        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_auth_validate_fail_timeout(self):
        port = 5523
        self.validated = False
        async def send_async_sec():
            authorized = await self.ironhouse.authenticate(self.fake['curve_key'], '127.0.0.1', port)
            self.assertEqual(authorized, 'no_reply')
            self.assertTrue(self.validated)
            self.ironhouse.cleanup()
            self.fake_ironhouse.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        def auth_validate_fake(vk):
            self.validated = True
            return False

        def auth_validate(vk):
            return vk == b'catastrophe'

        self.fake = genkeys('7ae3fcfd3a9047adbec6ad11e5a58036df9934dc0746431d80b49d25584d7e78')
        self.fake_ironhouse = Ironhouse(self.fake['sk'], wipe_certs=True, auth_validate=auth_validate, auth_port=port, keyname='fake')
        self.fake_ironhouse.setup_secure_server()
        self.fake_ironhouse.add_public_key(self.curve_public_key)
        self.fake_ironhouse.auth_validate = auth_validate_fake
        self.ironhouse.setup_secure_server()
        self.ironhouse.add_public_key(self.fake['curve_key'])
        self.ironhouse.auth_validate = auth_validate


        self.loop.run_until_complete(
            asyncio.ensure_future(
                send_async_sec()
            )
        )

    def test_cleanup(self):
        async def delay():
            await asyncio.sleep(0.1)
            del self.ironhouse
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.loop.run_until_complete(
            asyncio.ensure_future(
                delay()
            )
        )

    def tearDown(self):
        self.loop.close()

if __name__ == '__main__':
    unittest.main()
