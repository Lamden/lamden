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
from cilantro.constants.testnet import *
from tests.unit.protocol.overlay.ironhouse.base import TestIronhouseBase

def auth_validate(vk):
    print('Test: Received on validation: {}'.format(vk))
    return True

class TestConsts(TestIronhouseBase):
    def test_assert_paths(self):
        self.assertEqual(self.ironhouse.base_dir, 'certs/{}'.format(self.ironhouse.keyname), 'key folder is incorrect')
        self.assertEqual(self.ironhouse.authorized_keys_dir, 'certs/{}/authorized_keys'.format(self.ironhouse.keyname), 'public dir is incorrect')

    def test_generate_certificates_failed(self):
        self.ironhouse.wipe_certs = False
        shutil.rmtree(self.ironhouse.base_dir)
        self.ironhouse.generate_certificates(self.sk)
        self.assertTrue(listdir(self.ironhouse.authorized_keys_dir) == ['{}.key'.format(self.keyname)], 'public keys dir should not be created')

    def test_generate_certificates(self):
        self.ironhouse.generate_certificates(self.sk)
        self.assertTrue(listdir(self.ironhouse.authorized_keys_dir), 'public keys dir not created')
        self.assertEqual(self.private_key, decode(self.ironhouse.secret).hex(), 'secret key generation is incorrect')
        self.assertEqual(self.public_key, decode(self.ironhouse.public_key).hex(), 'public key generation is incorrect')

    def test_vk2pk(self):
        self.assertEqual(decode(self.ironhouse.vk2pk(self.vk)).hex(), self.public_key, 'conversion of vk to pk failed')

    def test_generate_from_private_key(self):
        makedirs(self.ironhouse.keys_dir, exist_ok=True)
        self.ironhouse.create_from_private_key(self.private_key, self.ironhouse.keyname)
        self.assertTrue(listdir(self.ironhouse.authorized_keys_dir), 'public keys dir not created')
        self.assertEqual(self.private_key, decode(self.ironhouse.secret).hex(), 'secret key generation is incorrect')
        self.assertEqual(self.public_key, decode(self.ironhouse.public_key).hex(), 'public key generation is incorrect')

    def test_generate_from_public_key(self):
        self.ironhouse.daemon_context, self.ironhouse.daemon_auth = self.ironhouse.secure_context(async=True)
        self.ironhouse.add_public_key(encode(self.public_key.encode()))
        self.assertTrue(listdir(self.ironhouse.authorized_keys_dir), 'public keys dir not created')
        self.assertTrue(exists('{}/{}.key'.format(self.ironhouse.authorized_keys_dir, self.keyname)), 'public key not generated')
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

if __name__ == '__main__':
    unittest.main()
