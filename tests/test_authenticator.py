from unittest import TestCase
import zmq.asyncio
import asyncio
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.core.sockets.authentication import SocketAuthenticator
import os
from zmq.utils import z85


class TestAuthenticator(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.w = Wallet()
        self.s = SocketAuthenticator(wallet=self.w, contacts=None, ctx=self.ctx)

    def tearDown(self):
        self.ctx.destroy()

        self.assertTrue(os.path.exists(self.s.cert_dir))
        self.s.flush_all_keys()
        self.assertFalse(os.path.exists(self.s.cert_dir))

    def test_double_init(self):
        w = Wallet()

        with self.assertRaises(Exception):
            b = SocketAuthenticator(wallet=w, contacts=None, ctx=self.ctx)

    def test_add_verifying_key_as_bytes(self):
        vk = b'\x00' * 32

        self.s.add_verifying_key(vk)

        self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{z85.encode(vk).decode("utf-8")}.key')))
