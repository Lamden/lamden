import json
from zmq.auth.asyncio import AsyncioAuthenticator
import zmq
import zmq.asyncio
import asyncio

from lamden.logger.base import get_logger
from lamden.crypto.z85 import z85_key
from typing import Callable
from lamden.crypto.wallet import Wallet

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

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

class Router():
    def __init__(self, wallet: Wallet = Wallet(), callback: Callable = None, logger = None):
        self.log = logger or get_logger('ROUTER')

        self.wallet = wallet
        self.callback = callback

        self.ctx = None
        self.socket = None
        self.auth = None
        self.cred_provider = CredentialsProvider()

        self.poller = zmq.asyncio.Poller()
        self.poll_time = 0.001

        self.running = False
        self.checking = False
        self.loop = None

        self.task_check_for_messages = None

        self.address = None
        self.set_address()

    @property
    def is_running(self) -> bool:
        return self.running

    @property
    def is_checking(self) -> bool:
        try:
            return not self.task_check_for_messages.done()
        except Exception:
            return False

    @property
    def socket_is_bound(self) -> bool:
        try:
            return len(self.socket.LAST_ENDPOINT) > 0
        except Exception:
            return False

    @property
    def socket_is_closed(self) -> bool:
        try:
            return self.socket.closed
        except Exception:
            return True

    @property
    def auth_is_stopped(self) -> bool:
        try:
            return self.auth._AsyncioAuthenticator__task.done()
        except AttributeError:
            return True

    @property
    def curve_server_setup(self) -> bool:
        try:
            return self.socket.CURVE_SERVER == 1
        except AttributeError:
            return False

    def set_address(self, ip: str = "*", port: int = 19000) -> None:
        if not isinstance(ip, str):
            raise TypeError(EXCEPTION_IP_NOT_TYPE_STR)

        if not isinstance(port, int):
            raise TypeError(EXCEPTION_PORT_NOT_TYPE_INT)

        self.address = f'tcp://{ip}:{port}'

    def setup_socket(self):
        self.ctx = zmq.asyncio.Context().instance()
        self.socket = self.ctx.socket(zmq.ROUTER)

    def setup_auth(self):
        #self.auth = ThreadAuthenticator(self.ctx)
        self.auth = AsyncioAuthenticator(self.ctx)
        self.auth.start()
        self.auth.configure_curve_callback(domain="*", credentials_provider=self.cred_provider)

    def register_poller(self):
        if not self.socket:
            raise AttributeError(EXCEPTION_NO_SOCKET)

        self.poller.register(self.socket, zmq.POLLIN)

    def setup_auth_keys(self):
        self.socket.curve_secretkey = self.wallet.curve_sk
        self.socket.curve_publickey = self.wallet.curve_vk
        self.socket.curve_server = True  # must come before bind

    def connect_socket(self):
        if not self.address:
            raise AttributeError(EXCEPTION_NO_ADDRESS_SET)

        if not self.socket:
            raise AttributeError(EXCEPTION_NO_SOCKET)

        self.socket.bind(self.address)

    def run_open_server(self):
        self.setup_socket()
        self.register_poller()
        self.connect_socket()

        self.task_check_for_messages = asyncio.ensure_future(self.check_for_messages())

    def run_curve_server(self):
        self.setup_socket()
        self.setup_auth()
        self.register_poller()
        self.setup_auth_keys()

        self.connect_socket()

        self.task_check_for_messages = asyncio.ensure_future(self.check_for_messages())

    async def has_message(self, timeout_ms: int = 10) -> bool:
        try:
            sockets = await self.poller.poll(timeout=timeout_ms)
            return self.socket in dict(sockets)
        except Exception:
            return False

    async def check_for_messages(self):
        self.running = True

        while self.is_running:
            if await self.has_message(timeout_ms=50):
                ident, empty, msg = await self.socket.recv_multipart()

                self.log.info(f"[ROUTER] Received request from {ident}: ", msg)

                try:
                    ident_vk_string = json.loads(ident.decode('UTF-8'))
                except Exception:
                    ident_vk_string = None

                if self.callback:
                    self.callback(ident_vk_string, msg)

    def send_msg(self, ident: str, msg):
        self.socket.send_multipart([ident, b'', msg])

    def close_socket(self):
        if not self.socket_is_closed:
            self.socket.setsockopt(zmq.LINGER, 0)
            self.socket.close()
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.wait_for_socket_to_close())

    async def stop_checking_for_messages(self):
        self.running = False
        while self.is_checking:
            await asyncio.sleep(self.poll_time / 1000)

    async def wait_for_socket_to_close(self):
        while not self.socket_is_closed:
            await asyncio.sleep(0.01)

    async def stop_auth(self):
        if self.auth_is_stopped:
            return

        self.auth.stop()

        while not self.auth_is_stopped:
            await asyncio.sleep(0.01)

    def stop(self):
        loop = asyncio.get_event_loop()

        loop.run_until_complete(self.stop_checking_for_messages())
        loop.run_until_complete(self.stop_auth())
        self.close_socket()

        self.log.info("[ROUTER] Stopped.")


