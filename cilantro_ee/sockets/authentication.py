from zmq.auth.asyncio import AsyncioAuthenticator
from zmq.error import ZMQBaseError
from zmq.auth.certs import _write_key_file, _cert_public_banner
from zmq.utils import z85
import shutil
import zmq.asyncio
import asyncio
import pathlib
from nacl.bindings import crypto_sign_ed25519_pk_to_curve25519
from cilantro_ee.logger.base import get_logger

CERT_DIR = 'cilsocks'


class SocketAuthenticator:
    def __init__(self, ctx: zmq.asyncio.Context,
                 loop=asyncio.get_event_loop(), domain='*', cert_dir=CERT_DIR, debug=True):

        # Create the directory if it doesn't exist

        self.cert_dir = pathlib.Path.home() / cert_dir
        self.cert_dir.mkdir(parents=True, exist_ok=True)

        self.ctx = ctx

        self.domain = domain

        self.loop = loop

        self.log = get_logger('zmq.auth')
        self.log.propagate = debug

        # This should throw an exception if the socket already exist
        try:
            self.authenticator = AsyncioAuthenticator(context=self.ctx, loop=self.loop)
            self.authenticator.start()
            self.authenticator.configure_curve(domain=self.domain, location=self.cert_dir)

        except ZMQBaseError:
            pass
            #raise Exception('AsyncioAuthenicator could not be started. Is it already running?')

    def add_governance_sockets(self, masternode_list, on_deck_masternode, delegate_list, on_deck_delegate):
        self.flush_all_keys()

        for mn in masternode_list:
            self.add_verifying_key(mn)

        for dl in delegate_list:
            self.add_verifying_key(dl)

        if on_deck_masternode is not None:
            self.add_verifying_key(on_deck_masternode)

        if on_deck_delegate is not None:
            self.add_verifying_key(on_deck_delegate)

        self.authenticator.configure_curve(domain=self.domain, location=self.cert_dir)

    def add_verifying_key(self, vk: bytes):
        # Convert to bytes if hex string
        if isinstance(vk, str):
            vk = bytes.fromhex(vk)

        try:
            pk = crypto_sign_ed25519_pk_to_curve25519(vk)
        # Error is thrown if the VK is not within the possibility space of the ED25519 algorithm
        except RuntimeError:
            print('no go')
            return

        zvk = z85.encode(pk).decode('utf-8')
        _write_key_file(self.cert_dir / f'{vk.hex()}.key', banner=_cert_public_banner, public_key=zvk)

    def flush_all_keys(self):
        shutil.rmtree(str(self.cert_dir))
        self.cert_dir.mkdir(parents=True, exist_ok=True)

