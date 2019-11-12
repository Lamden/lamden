from zmq.auth.asyncio import AsyncioAuthenticator
from zmq.error import ZMQBaseError
from zmq.auth.certs import _write_key_file, _cert_public_banner
from zmq.utils import z85
import os
from cilantro_ee.services.storage.vkbook import VKBook
import shutil
import zmq.asyncio
import asyncio
import pathlib

class SocketAuthenticator:
    def __init__(self, wallet, contacts: VKBook, ctx: zmq.asyncio.Context,
                 loop=asyncio.get_event_loop(), domain='*', cert_dir='.cilsocks'):

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

        zvk = z85.encode(vk).decode('utf-8')
        print(zvk)
        _write_key_file(self.cert_dir / f'{zvk}.key', banner=_cert_public_banner, public_key=zvk)

    def remove_public_key(self, vk: bytes):
        if isinstance(vk, str):
            hvk = vk

        # Store hex string if already bytes
        else:
            hvk = vk.hex()

        pathlib.Path.unlink(self.cert_dir / f'{hvk}.key')

    def flush_all_keys(self):
        shutil.rmtree(str(self.cert_dir))

    def make_socket(self, zmq_type, will_bind=False):
        sock = self.ctx.socket(zmq_type)
        sock.curve_secretkey = z85.encode(self.wallet.signing_key())
        sock.curve_publickey = z85.encode(self.wallet.verifying_key())

        sock.curve_server = will_bind

        return sock
