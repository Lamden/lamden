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
EXCEPTION_PORT_NOT_TYPE_INT = "port must be type int."
EXCEPTION_TO_VK_NOT_STRING = "to_vk is not type str."
EXCEPTION_MSG_NOT_STRING = "msg_str is not type str."

class CredentialsProvider(object):
    def __init__(self):
        self.approved_keys = {}

    def add_key(self, vk: str) -> None:
        self.approved_keys[vk] = z85_key(vk)
        self.log('info', f'Added {vk} to approved_keys.')

    def remove_key(self, vk: str) -> None:
        try:
            self.approved_keys.pop(vk)
            self.log('info', f'Removed {vk} from approved_keys.')
        except KeyError:
            pass

    def log(self, log_type: str, message: str) -> None:
        logger = get_logger('CREDENTIALS PROVIDER')
        if log_type == 'info':
            logger.info(message)
        if log_type == 'error':
            logger.error(message)
        if log_type == 'warning':
            logger.warning(message)

        print(f'[CREDENTIALS PROVIDER]{message}')

    def key_is_approved(self, curve_vk: bytes) -> bool:
        return curve_vk in self.approved_keys.values()

    def callback(self, domain: str, key: bytes) -> bool:
        if self.key_is_approved(curve_vk=key):
            self.log('info', f'Authorizing: {domain}, {key}')
            return True
        else:
            self.log('warning' f'NOT Authorizing: {domain}, {key}')
            return False

class Router():
    def __init__(self, wallet: Wallet = Wallet(), message_callback: Callable = None):
        self.wallet = wallet
        self.message_callback = message_callback

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
            return self.auth._AsyncioAuthenticator__task.done() and self.auth.zap_socket.closed
        except AttributeError:
            return True

    @property
    def curve_server_setup(self) -> bool:
        try:
            return self.socket.CURVE_SERVER == 1
        except AttributeError:
            return False

    def log(self, log_type: str, message: str) -> None:
        named_message = f'[ROUTER]{message}'

        logger = get_logger(f'{self.address}')
        if log_type == 'info':
            logger.info(named_message)
        if log_type == 'error':
            logger.error(named_message)
        if log_type == 'warning':
            logger.warning(named_message)

        print(f'[{self.address}]{named_message}')


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

        self.log('info', f'Started. on {self.address}')

    def run_curve_server(self):
        self.setup_socket()
        self.setup_auth()
        self.register_poller()
        self.setup_auth_keys()

        self.connect_socket()

        self.task_check_for_messages = asyncio.ensure_future(self.check_for_messages())

        self.log('info', f'Started. on {self.address}')

    async def has_message(self, timeout_ms: int = 10) -> bool:
        sockets = await self.poller.poll(timeout=timeout_ms)
        return self.socket in dict(sockets)

    async def check_for_messages(self):
        self.running = True

        while self.is_running:
            if await self.has_message(timeout_ms=50):
                ident_vk_bytes, empty, msg = await self.socket.recv_multipart()

                self.log('info', f'Received request from {ident_vk_bytes}: {msg}')

                try:
                    ident_vk_string = json.loads(ident_vk_bytes.decode('UTF-8'))
                except Exception:
                    ident_vk_string = None

                if self.message_callback:
                    self.message_callback(ident_vk_string, msg)

    def send_msg(self, to_vk: str, msg_str: str):
        if not self.socket:
            raise AttributeError(EXCEPTION_NO_SOCKET)

        if not isinstance(to_vk, str):
            raise AttributeError(EXCEPTION_TO_VK_NOT_STRING)

        if not isinstance(msg_str, str):
            raise AttributeError(EXCEPTION_MSG_NOT_STRING)

        ident_vk_bytes = json.dumps(to_vk).encode('UTF-8')

        self.socket.send_multipart([ident_vk_bytes, b'', msg_str.encode("UTF-8")])

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

        if self.auth.zap_socket:
            self.auth.zap_socket.close()

        while not self.auth_is_stopped:
            await asyncio.sleep(0.01)

    async def stop(self):
        await self.stop_checking_for_messages()
        await self.stop_auth()
        self.close_socket()

        self.log('info', 'Stopped.')


