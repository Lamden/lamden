from unittest import TestCase
import zmq.asyncio
import asyncio
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.core.sockets.authentication import SocketAuthenticator
import os
from zmq.utils import z85
from cilantro_ee.services.storage.vkbook import PhoneBook
from nacl.signing import SigningKey


class TestAuthenticator(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.w = Wallet()
        self.s = SocketAuthenticator(wallet=self.w, contacts=PhoneBook, ctx=self.ctx)

    def tearDown(self):
        self.ctx.destroy()
        #self.s.flush_all_keys()

    def test_double_init(self):
        w = Wallet()

        with self.assertRaises(Exception):
            b = SocketAuthenticator(wallet=w, contacts=None, ctx=self.ctx)

    def test_add_verifying_key_as_bytes(self):
        sk = SigningKey.generate()

        self.s.add_verifying_key(sk.verify_key.encode())

        self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{sk.verify_key.encode().hex()}.key')))

    def test_sync_certs_creates_files(self):
        self.s.sync_certs()

        for m in self.s.contacts.masternodes:
            self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{m}.key')))

        for d in self.s.contacts.delegates:
            self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{d}.key')))

    def test_make_client_works(self):
        w = Wallet()

        pub = self.ctx.socket(zmq.PUB)
        pub.curve_secretkey = w.curve_sk
        pub.curve_publickey = w.curve_vk

        pub.curve_server = True
        pub.setsockopt(zmq.LINGER, 1000)
        pub.bind('inproc://test1')

        self.s.add_verifying_key(w.verifying_key())

        sub = self.s.make_client(zmq.SUB, w.verifying_key())

        sub.setsockopt(zmq.SUBSCRIBE, b'')
        sub.connect('inproc://test1')

        async def get():
            msg = await sub.recv()
            return msg

        tasks = asyncio.gather(
            pub.send(b'hi'),
            get()
        )

        loop = asyncio.get_event_loop()
        _, msg = loop.run_until_complete(tasks)

        self.assertEqual(msg, b'hi')

    def test_make_server_works(self):
        w = Wallet()

        pub = self.s.make_server(zmq.PUB)
        pub.setsockopt(zmq.LINGER, 1000)
        pub.bind('inproc://test1')

        self.s.add_verifying_key(w.verifying_key())

        sub = self.s.make_client(zmq.SUB, w.verifying_key())

        sub.setsockopt(zmq.SUBSCRIBE, b'')
        sub.connect('inproc://test1')

        async def get():
            msg = await sub.recv()
            return msg

        tasks = asyncio.gather(
            pub.send(b'hi'),
            get()
        )

        loop = asyncio.get_event_loop()
        _, msg = loop.run_until_complete(tasks)

        self.assertEqual(msg, b'hi')