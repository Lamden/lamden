import json
import logging

from zmq.auth.asyncio import AsyncioAuthenticator
import zmq
import zmq.asyncio
import asyncio

from lamden.logger.base import get_logger
from lamden.crypto.z85 import z85_key
from typing import Callable
from lamden.crypto.wallet import Wallet
from lamden.sockets.monitor import SocketMonitor

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

EXCEPTION_NO_ADDRESS_SET = "Router address not set."
EXCEPTION_NO_SOCKET = "No socket created."
EXCEPTION_IP_NOT_TYPE_STR = "ip must be type string."
EXCEPTION_PORT_NOT_TYPE_INT = "port must be type int."
EXCEPTION_TO_VK_NOT_STRING = "to_vk is not type str."
EXCEPTION_IDENT_VK_BYTES_NOT_BYTES = "ident_vk_bytes is not type bytes"
EXCEPTION_MSG_NOT_STRING = "msg_str is not type str."

class CredentialsProvider(object):
    def __init__(self, network_ip: str = None):
        self.approved_keys = {}
        self.network_ip = network_ip
        self.accept_all = False

    def add_key(self, vk: str) -> None:
        self.approved_keys[vk] = z85_key(vk)
        # self.log('info', f'Added {vk} to approved_keys.')

    def remove_key(self, vk: str) -> None:
        try:
            self.approved_keys.pop(vk)
            self.log('info', f'Removed {vk} from approved_keys.')
        except KeyError:
            pass

    def log(self, log_type: str, message: str) -> None:
        if self.network_ip:
            named_message = f'[CREDENTIALS PROVIDER] {message}'
            print(f'[{self.network_ip}]{named_message}\n')
        else:
            named_message = message
            print(f'[CREDENTIALS PROVIDER] {named_message}\n')

        logger_name = self.network_ip or 'CREDENTIALS PROVIDER'
        logger = get_logger(logger_name)
        if log_type == 'info':
            logger.info(named_message)
        if log_type == 'error':
            logger.error(named_message)
        if log_type == 'warning':
            logger.warning(named_message)

    def key_is_approved(self, curve_vk: bytes) -> bool:
        return curve_vk in self.approved_keys.values()

    def callback(self, domain: str, key: bytes) -> bool:
        if self.accept_all or self.key_is_approved(curve_vk=key):
            self.log('info', f'Authorizing: {domain}, {key}')
            return True
        else:
            self.log('warning', f'NOT Authorizing: {domain}, {key}')
            return False

    def open_messages(self):
        self.accept_all = True

    def secure_messages(self):
        self.accept_all = False

class Router():
    def __init__(self, wallet: Wallet = Wallet(), message_callback: Callable = None, ctx: zmq.Context = None,
                 network_ip: str = None):
        self.wallet = wallet
        self.message_callback = message_callback

        self.network_ip = network_ip
        self.ctx = ctx
        self.socket = None
        self.auth = None
        self.cred_provider = CredentialsProvider(network_ip=network_ip)

        self.poller = zmq.asyncio.Poller()
        self.poll_time_ms = 10

        self.running = False
        self.should_check = False

        self.checking = False
        self.task_check_for_messages = None

        self.address = None
        self.set_address()

        self.socket_monitor = SocketMonitor(socket_type='ROUTER')
        #self.socket_monitor.start()

    @property
    def is_running(self) -> bool:
        return self.running

    @property
    def is_checking(self) -> bool:
        try:
            done = self.task_check_for_messages.done()
            return not done
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
            if self.auth._AsyncioAuthenticator__task is None:
                return self.auth.zap_socket.closed
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
        if self.network_ip:
            named_message = f'[ROUTER] {message}'
        else:
            named_message = message

        logger_name = self.network_ip or 'ROUTER'

        logger = get_logger(logger_name)
        if log_type == 'info':
            logger.info(named_message)
        if log_type == 'error':
            logger.error(named_message)
        if log_type == 'warning':
            logger.warning(named_message)

    def set_address(self, ip: str = "*", port: int = 19000) -> None:
        if not isinstance(ip, str):
            raise TypeError(EXCEPTION_IP_NOT_TYPE_STR)

        if not isinstance(port, int):
            raise TypeError(EXCEPTION_PORT_NOT_TYPE_INT)

        self.address = f'tcp://{ip}:{port}'

    def setup_socket(self):
        if not self.ctx:
            self.ctx = zmq.asyncio.Context().instance()
        self.socket = self.ctx.socket(zmq.ROUTER)
        if self.socket_monitor.running:
            self.socket_monitor.monitor(socket=self.socket)

        # self.socket.set(zmq.HWM, 2)
        # self.socket.set(zmq.TCP_KEEPALIVE, 1)
        # self.socket.set(zmq.LINGER, 0)

        self.socket.setsockopt(zmq.ROUTER_MANDATORY, 1)
        self.socket.setsockopt(zmq.RCVTIMEO, 10000)
        self.socket.setsockopt(zmq.RCVHWM, 10000)
        self.socket.setsockopt(zmq.SNDHWM, 10000)
        #self.socket.setsockopt(zmq.SNDTIMEO, 50000)

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

        self.running = True

        self.log('info', f'Started. on {self.address}')


    def run_curve_server(self):
        self.setup_socket()
        self.setup_auth()
        self.register_poller()
        self.setup_auth_keys()

        self.connect_socket()

        self.task_check_for_messages = asyncio.ensure_future(self.check_for_messages())
        # asyncio.ensure_future(self.router_is_checking_for_messages())

        self.running = True

        self.log('info', f'Started. on {self.address}')

    async def has_message(self, timeout_ms: int = 10) -> bool:
        # self.log('info', 'Checking for messages!')
        sockets = await self.poller.poll(timeout=timeout_ms)
        return self.socket in dict(sockets)

    async def check_for_messages(self):
        self.should_check = True

        while self.should_check:
            if await self.has_message(timeout_ms=self.poll_time_ms):
                multi_message = await self.socket.recv_multipart()
                self.log('info', f'multi_message: {multi_message}')
                ident_vk_bytes, empty, msg = multi_message

                self.log('info', f'Received request from {ident_vk_bytes}: {msg}')

                try:
                    ident_vk_string = json.loads(ident_vk_bytes.decode('UTF-8'))
                except Exception as err:
                    self.log('error', err)
                    ident_vk_string = None

                if self.message_callback:
                    asyncio.ensure_future(self.message_callback(
                        ident_vk_bytes=ident_vk_bytes,
                        ident_vk_string=ident_vk_string,
                        msg=msg
                    ))

                await asyncio.sleep(0)
            else:
                await asyncio.sleep(0.1)
                # self.log('info', 'No Messages Found!')

        self.log('info', 'Stopped Checking for messages.')

    async def router_is_checking_for_messages(self):
        while self.running:
            await asyncio.sleep(120)
            self.log('info', f'should check {self.should_check}, task_check_for_messages.done(): {self.task_check_for_messages.done()}')
            self.log('info', f'currently approved in cred manager: {self.cred_provider.approved_keys}')

    def send_msg(self, ident_vk_bytes: bytes, to_vk: str, msg_str: str):
        if not self.socket:
            raise AttributeError(EXCEPTION_NO_SOCKET)

        if not isinstance(to_vk, str):
            raise AttributeError(EXCEPTION_TO_VK_NOT_STRING)

        if not isinstance(ident_vk_bytes, bytes):
            raise AttributeError(EXCEPTION_IDENT_VK_BYTES_NOT_BYTES)

        if not isinstance(msg_str, str):
            raise AttributeError(EXCEPTION_MSG_NOT_STRING)

        asyncio.ensure_future(self.async_send(
            ident_vk_bytes=ident_vk_bytes,
            to_vk=to_vk,
            msg_str=msg_str
        ))

    async def async_send(self, ident_vk_bytes: bytes, to_vk: str, msg_str: str):
        try:
            await self.socket.send_multipart([ident_vk_bytes, b'', msg_str.encode("UTF-8")])
            self.log('info', f'Sent Message Back to {to_vk}. {msg_str}')
        except Exception as err:
            self.log('error', f'error sending multipart message back to {to_vk}. {ident_vk_bytes} {msg_str}')
            self.log('error', err)


    def refresh_cred_provider_vks(self, vk_list: list = []) -> None:
        for vk in vk_list:
            self.cred_provider.add_key(vk=vk)

        current_vks = list(self.cred_provider.approved_keys.keys())
        for vk in current_vks:
            if vk not in vk_list:
                self.cred_provider.remove_key(vk=vk)

    async def close_socket(self):
        if self.socket_monitor.running:
            self.socket_monitor.stop_monitoring(socket=self.socket)

        if not self.socket_is_closed:
            self.socket.setsockopt(zmq.LINGER, 0)
            self.socket.close()
            await self.wait_for_socket_to_close()

    async def stop_checking_for_messages(self):
        try:
            self.should_check = False
            while self.is_checking:
                await asyncio.sleep(self.poll_time_ms / 1000)
        except Exception as err:
            print(err)

    async def wait_for_socket_to_close(self):
        while not self.socket_is_closed:
            await asyncio.sleep(0.01)

    async def stop_auth(self):
        if self.auth_is_stopped:
            return

        while not self.auth_is_stopped:
            try:
                self.auth.stop()
                if self.auth.zap_socket:
                    self.auth.zap_socket.close()
            except:
                pass
            await asyncio.sleep(0.01)

    async def stop(self):
        try:
            await self.stop_checking_for_messages()
            await self.stop_auth()
            await self.close_socket()
            if self.socket_monitor.running:
                await self.socket_monitor.stop()
        except Exception as err:
            print(err)

        self.running = False
        self.log('info', 'Stopped.')


