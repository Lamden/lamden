import unittest
from unittest import TestCase
import zmq, zmq.asyncio, asyncio
from zmq.auth.thread import ThreadAuthenticator
from zmq.auth.asyncio import AsyncioAuthenticator
from cilantro.protocol.overlay.ironhouse import Ironhouse
from zmq.utils.z85 import decode, encode
from os import listdir
from os.path import exists
from threading import Timer
import asyncio, shutil

class TestIronhouse(TestCase):
    def setUp(self):
        def auth_validate(public_key):
            print('Test: Received on validation: {}'.format(public_key))
            return True
        self.sk = '06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a'
        self.vk = '82540bb5a9c84162214c5540d6e43be49bbfe19cf49685660cab608998a65144'
        self.private_key = 'f0ca3d349e56e419e72f11c1fd734ae929a483f9490907d2ded554d9f794f361'
        self.public_key = '73619fa1464ce16802b480a0fd7868ffcce0f7285050a927a07ef1ffdd34c162'
        self.curve_public_key = b'B77YmmOI=O0<)GJ@DJ2Q+&5jzp/absPNMCh?88@S'
        self.ironhouse = Ironhouse(self.sk, wipe_certs=True, auth_validate=auth_validate)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def test_assert_paths(self):
        self.assertEqual(self.ironhouse.base_dir, 'certs/ironhouse', 'key folder is incorrect')
        self.assertEqual(self.ironhouse.keys_dir, 'certs/ironhouse/certificates', 'keys dir is incorrect')
        self.assertEqual(self.ironhouse.public_keys_dir, 'certs/ironhouse/public_keys', 'public dir is incorrect')
        self.assertEqual(self.ironhouse.secret_keys_dir, 'certs/ironhouse/private_keys', 'secret dir is incorrect')
        self.assertEqual(self.ironhouse.secret_file, 'certs/ironhouse/private_keys/ironhouse.key_secret', 'secret_file is incorrect')

    def test_generate_certificates_failed(self):
        self.ironhouse.wipe_certs = False
        shutil.rmtree(self.ironhouse.base_dir)
        self.ironhouse.generate_certificates(self.sk)
        self.assertFalse(listdir(self.ironhouse.public_keys_dir), 'public keys dir should not be created')
        self.assertFalse(listdir(self.ironhouse.secret_keys_dir), 'secret keys dir should not be created')
        self.assertTrue(listdir(self.ironhouse.keys_dir)==[], 'certificate keys dir should not be created')

    def test_generate_certificates(self):
        self.ironhouse.generate_certificates(self.sk)
        self.assertTrue(listdir(self.ironhouse.public_keys_dir), 'public keys dir not created')
        self.assertTrue(listdir(self.ironhouse.secret_keys_dir), 'secret keys dir not created')
        self.assertTrue(listdir(self.ironhouse.keys_dir)==[], 'certificate keys is not empty')
        self.assertTrue(exists(self.ironhouse.secret_file), 'secret keys not created')
        self.assertEqual(self.private_key, decode(self.ironhouse.secret).hex(), 'secret key generation is incorrect')
        self.assertEqual(self.public_key, decode(self.ironhouse.public).hex(), 'public key generation is incorrect')

    def test_vk2pk(self):
        self.assertEqual(decode(self.ironhouse.vk2pk(self.vk)).hex(), self.public_key, 'conversion of vk to pk failed')

    def test_generate_from_private_key(self):
        self.ironhouse.create_from_private_key(self.private_key)
        self.assertTrue(listdir(self.ironhouse.public_keys_dir), 'public keys dir not created')
        self.assertTrue(listdir(self.ironhouse.secret_keys_dir), 'secret keys dir not created')
        self.assertTrue(listdir(self.ironhouse.keys_dir), 'certificate keys dir not created')
        self.assertTrue(exists(self.ironhouse.secret_file), 'secret keys not created')
        self.assertEqual(self.private_key, decode(self.ironhouse.secret).hex(), 'secret key generation is incorrect')
        self.assertEqual(self.public_key, decode(self.ironhouse.public).hex(), 'public key generation is incorrect')

    def test_generate_from_public_key(self):
        self.ironhouse.create_from_public_key(encode(self.public_key.encode()))
        self.assertTrue(listdir(self.ironhouse.public_keys_dir), 'public keys dir not created')
        self.assertTrue(exists('{}/ironhouse.key'.format(self.ironhouse.public_keys_dir)), 'public key not generated')

    def test_secure_context_async(self):
        ctx, auth = self.ironhouse.secure_context(async=True)
        self.assertIsInstance(ctx, zmq.asyncio.Context, 'asynchronous context created incorrectly')
        self.assertIsInstance(auth, AsyncioAuthenticator, 'synchronous auth object created incorrectly')
        auth.stop()

    def test_secure_context_sync(self):
        ctx, auth = self.ironhouse.secure_context(async=False)
        self.assertIsInstance(ctx, zmq.Context, 'synchronous context created incorrectly')
        self.assertIsInstance(auth, ThreadAuthenticator, 'synchronous auth object created incorrectly')
        auth.stop()

    def test_secure_socket_sync(self):
        ctx, auth = self.ironhouse.secure_context(async=False)
        sock = ctx.socket(zmq.REP)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure REP socket')

        sock = ctx.socket(zmq.REQ)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure REQ socket')

        sock = ctx.socket(zmq.PUSH)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure PUSH socket')

        sock = ctx.socket(zmq.PULL)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure PULL socket')

        sock = ctx.socket(zmq.DEALER)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure DEALER socket')

        sock = ctx.socket(zmq.ROUTER)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure ROUTER socket')

        sock = ctx.socket(zmq.PUB)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure PUB socket')

        sock = ctx.socket(zmq.SUB)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure SUB socket')

        auth.stop()

    def test_secure_socket_async(self):
        ctx, auth = self.ironhouse.secure_context(async=True)
        sock = ctx.socket(zmq.REP)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure REP socket')

        sock = ctx.socket(zmq.REQ)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure REQ socket')

        sock = ctx.socket(zmq.PUSH)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure PUSH socket')

        sock = ctx.socket(zmq.PULL)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure PULL socket')

        sock = ctx.socket(zmq.DEALER)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure DEALER socket')

        sock = ctx.socket(zmq.ROUTER)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure ROUTER socket')

        sock = ctx.socket(zmq.PUB)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=None)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure PUB socket')

        sock = ctx.socket(zmq.SUB)
        sec_sock = self.ironhouse.secure_socket(sock, curve_serverkey=self.curve_public_key)
        self.assertIsInstance(sec_sock, zmq.sugar.socket.Socket, 'unable to secure SUB socket')

        auth.stop()

    def test_reconfigure_curve(self):
        ctx, auth = self.ironhouse.secure_context(async=True)
        self.ironhouse.daemon_auth = auth
        sock = ctx.socket(zmq.REP)
        sec_sock = self.ironhouse.secure_socket(sock)
        self.assertIn(self.curve_public_key, auth.certs['*'].keys(), 'cannot find cert in auth')

    def test_secure_server(self):
        def send_sec_req():
            ip = '127.0.0.1'
            port = 4523
            client = self.ironhouse.ctx.socket(zmq.REQ)
            client = self.ironhouse.secure_socket(client, self.curve_public_key)
            client.connect('tcp://{}:{}'.format(ip, port))
            client.send(self.curve_public_key)

            msg = None
            if client.poll(1000):
                msg = client.recv()

            client.close()
            self.ironhouse.cleanup()
            self.assertEqual(msg, b'B77YmmOI=O0<)GJ@DJ2Q+&5jzp/absPNMCh?88@S')
            self.loop.stop()

        self.ironhouse.setup_secure_server()
        self.assertIsInstance(self.ironhouse.ctx, zmq.Context, 'asynchronous context created incorrectly')
        self.assertIsInstance(self.ironhouse.sec_sock, zmq.sugar.socket.Socket, 'unable to secure a socket')

        t = Timer(0.01, send_sec_req)
        t.start()
        self.loop.run_forever()

    def test_authenticate(self):
        def send_sec_req():
            self.assertTrue(self.ironhouse.authenticate(self.curve_public_key, '127.0.0.1'))
            self.ironhouse.cleanup()
            self.loop.stop()

        self.ironhouse.setup_secure_server()
        self.assertIsInstance(self.ironhouse.ctx, zmq.Context, 'asynchronous context created incorrectly')
        self.assertIsInstance(self.ironhouse.sec_sock, zmq.sugar.socket.Socket, 'unable to secure a socket')

        t = Timer(0.01, send_sec_req)
        t.start()
        self.loop.run_forever()

    def test_authenticate_fail(self):
        def send_sec_req():
            self.assertFalse(self.ironhouse.authenticate(b'A/c=Kn2)aHRI*>fK-{v*r^YCyXJ//3.CGQQC@A9J', '127.0.0.1'))
            self.ironhouse.cleanup()
            self.loop.stop()

        self.ironhouse.setup_secure_server()

        t = Timer(0.01, send_sec_req)
        t.start()
        self.loop.run_forever()

    def test_auth_validate(self):
        def send_sec_req():
            self.assertTrue(self.ironhouse.authenticate(self.curve_public_key, '127.0.0.1'))
            self.ironhouse.cleanup()
            self.loop.stop()

        def auth_validate(public_key):
            return public_key == b'B77YmmOI=O0<)GJ@DJ2Q+&5jzp/absPNMCh?88@S'

        self.ironhouse.auth_validate = auth_validate
        self.ironhouse.setup_secure_server()
        self.assertIsInstance(self.ironhouse.ctx, zmq.Context, 'asynchronous context created incorrectly')
        self.assertIsInstance(self.ironhouse.sec_sock, zmq.sugar.socket.Socket, 'unable to secure a socket')

        t = Timer(0.01, send_sec_req)
        t.start()
        self.loop.run_forever()

    def test_auth_validate_fail(self):
        def send_sec_req():
            self.assertFalse(self.ironhouse.authenticate(self.curve_public_key, '127.0.0.1'))
            self.ironhouse.cleanup()
            self.loop.stop()

        def auth_validate(public_key):
            return public_key == b'A/c=Kn2)aHRI*>fK-{v*r^YCyXJ//3.CGQQC@A9J'

        self.ironhouse.auth_validate = auth_validate
        self.ironhouse.setup_secure_server()
        self.assertIsInstance(self.ironhouse.ctx, zmq.Context, 'asynchronous context created incorrectly')
        self.assertIsInstance(self.ironhouse.sec_sock, zmq.sugar.socket.Socket, 'unable to secure a socket')

        t = Timer(0.01, send_sec_req)
        t.start()
        self.loop.run_forever()

    def tearDown(self):
        self.loop.close()

if __name__ == '__main__':
    unittest.main()
