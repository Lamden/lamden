from zmq.auth.asyncio import AsyncioAuthenticator
from zmq.error import ZMQBaseError
from zmq.auth.certs import _write_key_file, _cert_public_banner, load_certificate
from zmq.utils import z85
from cilantro_ee.storage.vkbook import VKBook
import shutil
import zmq.asyncio
import asyncio
import pathlib
from nacl.bindings import crypto_sign_ed25519_pk_to_curve25519


class SocketAuthenticator:
    def __init__(self, wallet, contacts: VKBook, ctx: zmq.asyncio.Context,
                 loop=asyncio.get_event_loop(), domain='*', cert_dir='cilsocks'):

        # Create the directory if it doesn't exist

        self.cert_dir = pathlib.Path.home() / cert_dir
        self.cert_dir.mkdir(parents=True, exist_ok=True)

        self.wallet = wallet
        self.ctx = ctx
        self.contacts = contacts

        self.domain = domain

        self.loop = loop

        # This should throw an exception if the socket already exist
        try:
            self.authenticator = AsyncioAuthenticator(context=self.ctx, loop=self.loop)
            self.authenticator.start()
            self.authenticator.configure_curve(domain=self.domain, location=self.cert_dir)

        except ZMQBaseError:
            raise Exception('AsyncioAuthenicator could not be started. Is it already running?')

    def sync_certs(self):
        self.flush_all_keys()

        for m in self.contacts.masternodes:
            self.add_verifying_key(m)

        for d in self.contacts.delegates:
            self.add_verifying_key(d)

        self.authenticator.configure_curve(domain=self.domain, location=self.cert_dir)

    def add_verifying_key(self, vk: bytes):
        # Convert to bytes if hex string
        if isinstance(vk, str):
            vk = bytes.fromhex(vk)

        try:
            pk = crypto_sign_ed25519_pk_to_curve25519(vk)
        # Error is thrown if the VK is not within the possibility space of the ED25519 algorithm
        except RuntimeError:
            return

        zvk = z85.encode(pk).decode('utf-8')
        _write_key_file(self.cert_dir / f'{vk.hex()}.key', banner=_cert_public_banner, public_key=zvk)

    def flush_all_keys(self):
        shutil.rmtree(str(self.cert_dir))
        self.cert_dir.mkdir(parents=True, exist_ok=True)

    def make_client(self, zmq_type, server_vk: bytes):
        sock = self.ctx.socket(zmq_type)
        sock.curve_secretkey = self.wallet.curve_sk
        sock.curve_publickey = self.wallet.curve_vk

        server_pub, _ = load_certificate(str(self.cert_dir / f'{server_vk.hex()}.key'))

        sock.curve_serverkey = server_pub

        return sock

    def make_server(self, zmq_type):
        sock = self.ctx.socket(zmq_type)
        sock.curve_secretkey = self.wallet.curve_sk
        sock.curve_publickey = self.wallet.curve_vk

        sock.curve_server = True

        return sock