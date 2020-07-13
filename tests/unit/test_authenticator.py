from unittest import TestCase
import zmq.asyncio
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.authentication import SocketAuthenticator
import os
from nacl.signing import SigningKey
from cilantro_ee.contracts import sync
import cilantro_ee
from contracting.client import ContractingClient


class TestAuthenticator(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.w = Wallet()

        self.masternodes = [Wallet().verifying_key, Wallet().verifying_key, Wallet().verifying_key]
        self.delegates = [Wallet().verifying_key, Wallet().verifying_key, Wallet().verifying_key]

        self.c = ContractingClient()
        self.c.flush()

        sync.setup_genesis_contracts(self.masternodes, self.delegates, client=self.c)

    def tearDown(self):
        self.ctx.destroy()

        self.c.flush()

    def test_add_verifying_key_writes_file(self):
        s = SocketAuthenticator(client=self.c, ctx=self.ctx)

        sk = SigningKey.generate()

        s.add_verifying_key(sk.verify_key.encode().hex())

        s.authenticator.stop()

        self.assertTrue(os.path.exists(os.path.join(s.cert_dir, f'{sk.verify_key.encode().hex()}.key')))

    def test_add_verifying_key_invalid_does_nothing(self):
        sk = b'\x00' * 32

        s = SocketAuthenticator(client=self.c, ctx=self.ctx)
        s.add_verifying_key(sk.hex())
        s.authenticator.stop()

        self.assertFalse(os.path.exists(os.path.join(s.cert_dir, f'{sk.hex()}.key')))

    def test_add_governance_sockets_all_creates_files(self):
        fake_mns = [
            Wallet().verifying_key,
            Wallet().verifying_key,
            Wallet().verifying_key
        ]

        self.c.set_var(
            contract='masternodes',
            variable='S',
            arguments=['members'],
            value=fake_mns
        )

        fake_dels = [
            Wallet().verifying_key,
            Wallet().verifying_key
        ]

        self.c.set_var(
            contract='delegates',
            variable='S',
            arguments=['members'],
            value=fake_dels
        )

        s = SocketAuthenticator(client=self.c, ctx=self.ctx)
        s.refresh_governance_sockets()
        s.authenticator.stop()

        for m in fake_mns:
            self.assertTrue(os.path.exists(os.path.join(s.cert_dir, f'{m}.key')))

        for d in fake_dels:
            self.assertTrue(os.path.exists(os.path.join(s.cert_dir, f'{d}.key')))

    def test_passing_bootnodes_adds_keys_on_initialization(self):
        w1 = Wallet()
        w2 = Wallet()
        w3 = Wallet()

        bootnodes = {
            w1.verifying_key: '127.0.0.1:18000',
            w2.verifying_key: '127.0.0.1:18001',
            w3.verifying_key: '127.0.0.1:18002',
        }

        s = SocketAuthenticator(client=self.c, ctx=self.ctx, bootnodes=bootnodes)

        self.assertTrue(os.path.exists(os.path.join(s.cert_dir, f'{w1.verifying_key}.key')))
        self.assertTrue(os.path.exists(os.path.join(s.cert_dir, f'{w2.verifying_key}.key')))
        self.assertTrue(os.path.exists(os.path.join(s.cert_dir, f'{w3.verifying_key}.key')))
