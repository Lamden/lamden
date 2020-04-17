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

    def sync_certs(self):
        self.flush_all_keys()

        for m in self.contacts.masternodes:
            self.add_verifying_key(m)

        for d in self.contacts.delegates:
            self.add_verifying_key(d)

        self.authenticator.configure_curve(domain=self.domain, location=self.cert_dir)

    def configure(self):
        self.authenticator.configure_curve(domain=self.domain, location=self.cert_dir)

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

    # def update_sockets(self):
    #     # UPDATE SOCKETS IF NEEDED
    #     mn = self.elect_masternodes.quick_read('top_candidate')
    #     dl = self.elect_delegates.quick_read('top_candidate')
    #
    #     self.log.info(f'Top MN is {mn}')
    #     self.log.info(f'Top DL is {dl}')
    #
    #     update_mn = self.on_deck_master != mn and mn is not None
    #     update_del = self.on_deck_delegate != dl and dl is not None
    #
    #     ## Check if
    #     nodes_changed = self.contacts.masternodes != self.current_masters \
    #                     or self.contacts.delegates != self.current_delegates
    #
    #     if nodes_changed:
    #         self.current_masters = deepcopy(self.contacts.masternodes)
    #         self.current_delegates = deepcopy(self.contacts.delegates)
    #
    #     if update_mn or update_del or nodes_changed:
    #         self.socket_authenticator.sync_certs()
    #
    #         if update_mn:
    #             self.log.info(f'Adding on deck master {mn}')
    #             self.socket_authenticator.add_verifying_key(bytes.fromhex(mn))
    #             self.on_deck_master = mn
    #
    #         if update_del:
    #             self.log.info(f'Adding on deck delegate {dl}')
    #             self.socket_authenticator.add_verifying_key(bytes.fromhex(dl))
    #             self.on_deck_delegate = dl
    #
    #     self.socket_authenticator.configure()