import asyncio
import json
from time import sleep
import zmq
import zmq.asyncio
import threading

from typing import Callable

from lamden.logger.base import get_logger
from zmq.auth.asyncio import AsyncioAuthenticator
from lamden.crypto.wallet import Wallet
from lamden.crypto.z85 import z85_key

EXCEPTION_NO_ADDRESS_SET = "Router address not set."
EXCEPTION_NO_SOCKET = "No socket created."
EXCEPTION_IP_NOT_TYPE_STR = "ip must be type string."
EXCEPTION_PORT_NOT_TYPE_INT = "port must be type int"


class CredentialsProvider(object):
    def __init__(self):
        self.log = get_logger("CREDENTIALS PROVIDER")
        self.approved_keys = {}

    def add_key(self, vk: str) -> None:
        self.approved_keys[vk] = z85_key(vk)

    def remove_key(self, vk: str) -> None:
        try:
            self.approved_keys.pop(vk)
        except KeyError:
            pass

    def key_is_approved(self, curve_vk: bytes) -> bool:
        return curve_vk in self.approved_keys.values()

    def callback(self, domain: str, key: bytes) -> bool:
        if self.key_is_approved(curve_vk=key):
            print(f'[{self.log.name}][ROUTER] Authorizing: {domain}, {key}')
            self.log.info(f'[ROUTER] Authorizing: {domain}, {key}')

            return True
        else:
            print(f'[{self.log.name}][ROUTER] NOT Authorizing: {domain}, {key}')
            self.log.warning(f'[ROUTER] NOT Authorizing: {domain}, {key}')

            return False


class Router:
    def __init__(self, router_wallet: Wallet = None, callback: Callable = None, logger=None):
        self.log = logger or get_logger('ROUTER')
        self.ctx = None
        self.socket = None
        self.address = None
        self.wallet = router_wallet or Wallet()
        self.running = False
        self.paused = False # For testing
        self.credentials_provider = CredentialsProvider()
        self.auth = None
        self.callback = callback
        self.loop = None

        self.poller = None
        self.poll_time = 500

    def __del__(self):
        print(f'[{self.log.name}][ROUTER] Destroyed')
        self.log.info(f'[ROUTER] Destroyed')

    @property
    def is_paused(self):
        return self.paused

    @property
    def socket_is_bound(self) -> bool:
        try:
            return len(self.socket.LAST_ENDPOINT) > 0
        except Exception as err:
            return False

    @property
    def socket_is_closed(self) -> bool:
        try:
            return self.socket.closed
        except AttributeError:
            return True

    @property
    def curve_server_setup(self) -> bool:
        try:
            return self.socket.CURVE_SERVER == 1
        except AttributeError:
            return False

    def setup_event_loop(self) -> None:
        try:
            self.loop = asyncio.get_event_loop()
            if self.loop._closed:
                raise AttributeError
        except Exception:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def create_context(self) -> None:
        self.ctx = zmq.asyncio.Context().instance()

    def create_socket(self) -> None:
        if not self.ctx:
            self.create_context()
        self.socket = self.ctx.socket(zmq.ROUTER)

    def set_address(self, ip: str = "*", port: int = 19080) -> None:
        if not isinstance(ip, str):
            raise TypeError(EXCEPTION_IP_NOT_TYPE_STR)

        if not isinstance(port, int):
            raise TypeError(EXCEPTION_PORT_NOT_TYPE_INT)

        self.address = f'tcp://{ip}:{port}'

    def connect_socket(self) -> None:
        if not self.address:
            raise AttributeError(EXCEPTION_NO_ADDRESS_SET)

        if not self.socket:
            raise AttributeError(EXCEPTION_NO_SOCKET)

        self.socket.bind(self.address)

    def setup_authentication_keys(self) -> None:
        if not self.socket:
            raise AttributeError(EXCEPTION_NO_SOCKET)

        self.socket.curve_secretkey = self.wallet.curve_sk
        self.socket.curve_publickey = self.wallet.curve_vk
        self.socket.curve_server = True  # must come before bind

    def setup_authentication(self) -> None:
        if not self.ctx:
            self.create_context()

        self.auth = AsyncioAuthenticator(self.ctx)
        self.auth.start()
        self.auth.configure_curve_callback(domain="*", credentials_provider=self.credentials_provider)

    def create_poller(self) -> None:
        if not self.socket:
            raise AttributeError(EXCEPTION_NO_SOCKET)

        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)

    def start(self) -> None:
        print(f'[{self.log.name}][ROUTER] Starting on: ' + self.address)
        self.log.info('[ROUTER] Starting on: ' + self.address)

        # Start an authenticator for this context.
        self.create_context()
        self.setup_event_loop()
        self.create_socket()
        self.setup_authentication_keys()
        self.setup_authentication()
        self.connect_socket()

        asyncio.ensure_future(self.check_for_messages())

        # Create a poller to monitor if there is any

    async def has_message(self, timeout: int = 10) -> bool:
        return await self.socket.poll(timeout=timeout, flags=zmq.POLLIN) > 0

    async def check_for_messages(self) -> None:
        self.running = True

        while self.running:
            if self.is_paused:
                await asyncio.sleep(1)
            else:
                if await self.has_message(timeout=50):
                    peer_ident_curve_vk, empty, msg = await self.socket.recv_multipart()

                    print(f'[{self.log.name}][ROUTER] received: {peer_ident_curve_vk}] {msg}')
                    self.log.info(f'[ROUTER] {peer_ident_curve_vk} {msg}')

                    # print('Router received %s from %s' % (msg, ident))
                    if self.callback is not None:
                        self.callback(self, peer_ident_curve_vk=peer_ident_curve_vk, msg_obj=json.loads(msg))

    def send_msg(self, peer_ident_curve_vk: str, msg_bytes: bytes) -> None:
        self.socket.send_multipart([peer_ident_curve_vk, b'', msg_bytes])

    def pause(self) -> None:
        self.paused = True

    def unpause(self) -> None:
        self.paused = False

    def close_socket(self) -> None:
        if not self.socket:
            return
        self.socket.close()

    async def stopping(self) -> None:
        while not self.socket_is_closed:
            await asyncio.sleep(0)

    def stop(self) -> None:
        self.running = False
        self.unpause()

        if not self.socket:
            return

        if self.auth:
            self.auth.stop()

        if not self.socket_is_closed:
            self.close_socket()
            self.setup_event_loop()
            self.loop.run_until_complete(self.stopping())

        self.log.info('[ROUTER] Stopped.')
        print(f'[{self.log.name}][ROUTER] Stopped.')