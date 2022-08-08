import asyncio

import zmq
import zmq.asyncio
from lamden.logger.base import get_logger
from lamden.crypto.wallet import Wallet
from contracting.db.encoder import encode
from lamden.sockets.monitor import SocketMonitor
from typing import Callable

ATTRIBUTE_ERROR_TO_ADDRESS_NOT_NONE = "to_address property cannot be none."

class Lock:
    def __init__(self):
        self.lock = False

    async def __aenter__(self):
        while self.lock:
            await asyncio.sleep(0)

        self.lock = True

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.lock = False


class Result:
    def __init__(self, success, response=None, error=None):
        self.success = success
        self.response = response
        self.error = error

class Request():
    def __init__(self, to_address: str, server_curve_vk: int = None, local_wallet: Wallet = None, ctx: zmq.Context = None,
                 local_ip: str = None, reconnect_callback: Callable = None):
        self.ctx = ctx or zmq.asyncio.Context().instance()

        self.to_address = to_address

        self.running = True


        self.local_ip = local_ip
        self.local_wallet = local_wallet or Wallet()
        self.server_curve_vk = server_curve_vk

        self.socket = None
        self.pollin = None
        self.lock = Lock()

        self.socket_monitor = SocketMonitor(
            socket_type="REQUEST",
            parent_ip=self.local_ip
        )
        self.socket_monitor.start()

    @property
    def is_running(self) -> bool:
        return self.running

    @property
    def secure_socket(self) -> bool:
        return self.server_curve_vk is not None

    @property
    def id(self) -> str:
        return self.local_wallet.verifying_key

    def log(self, log_type: str, message: str) -> None:
        if self.local_ip:
            named_message = f'[REQUEST] {message}'
            logger = get_logger(self.local_ip)
        else:
            named_message = message
            logger = get_logger(f'REQUEST')

        if log_type == 'info':
            logger.info(named_message)
        if log_type == 'error':
            logger.error(named_message)
        if log_type == 'warning':
            logger.warning(named_message)

    def socket_is_bound(self) -> bool:
        try:
            return len(self.socket.LAST_ENDPOINT) > 0
        except AttributeError:
            return False

    def create_socket(self) -> None:
        self.socket = self.ctx.socket(zmq.REQ)

    def set_socket_options(self) -> None:
        pass
        # self.socket.setsockopt(zmq.RCVTIMEO, 1000)

    def setup_secure_socket(self) -> None:
        if not self.secure_socket:
            raise AttributeError("Provided server_curve_vk for a secure socket connection.")

        self.socket.curve_secretkey = self.local_wallet.curve_sk
        self.socket.curve_publickey = self.local_wallet.curve_vk
        self.socket.curve_serverkey = self.server_curve_vk
        self.socket.identity = encode(self.id).encode()

    def setup_polling(self) -> None:
        self.pollin = zmq.asyncio.Poller()
        self.pollin.register(self.socket, zmq.POLLIN)

    def connect_socket(self) -> None:
        self.socket.connect(self.to_address)

    def send_string(self, str_msg: str) -> None:
        if not self.socket:
            raise AttributeError("Socket has not been created.")

        if not self.socket_is_bound():
            raise AttributeError("Socket is not bound to an address.")

        if not isinstance(str_msg, str):
            raise TypeError("Message Must be string.")

        return self.socket.send_string(str_msg)

    async def message_waiting(self, poll_time: int) -> bool:
        try:
            sockets = await self.pollin.poll(timeout=poll_time)
            return self.socket in dict(sockets)
        except:
            return False

    def start(self):
        if self.to_address is None:
            raise AttributeError(ATTRIBUTE_ERROR_TO_ADDRESS_NOT_NONE)

        self.create_socket()

        self.socket_monitor.monitor(socket=self.socket)

        if self.secure_socket:
            self.setup_secure_socket()

        self.setup_polling()

        self.set_socket_options()

        self.connect_socket()

    async def send(self, str_msg: str, timeout: int = 2500, attempts: int = 3) -> Result:
        async with self.lock:
            error = None
            connection_attempts = 0

            while connection_attempts < attempts:

                self.log('info', f'Attempt {connection_attempts + 1}/{attempts} to {self.to_address}; sending {str_msg}')

                if not self.running:
                    break

                try:
                    self.send_string(str_msg=str_msg)

                    if await self.message_waiting(poll_time=timeout):

                        response = await self.socket.recv()

                        self.log('info', '%s received: %s' % (self.id, response))

                        return Result(success=True, response=response)

                    else:
                        self.log('warning', f'No response from {self.to_address} in poll time.')
                        self.reconnect_socket()

                except zmq.ZMQError as err:
                    if err.errno == zmq.ETERM:
                        self.log('error', f'Interrupted: {err.strerror}')
                        break  # Interrupted

                    else:
                        self.log('error', err.strerror)
                        error = err.strerror

                except TypeError as err:
                    self.log('error', err)
                    error = str(err)
                    break

                except Exception as err:
                    self.log('error', err)
                    error = str(err)

                connection_attempts += 1

                await asyncio.sleep(0)

            if not error:
                error = f'Request Socket Error: Failed to receive response after {attempts} attempts each waiting {timeout}ms'

            return Result(success=False, error=error)

    def reconnect_socket(self):
        self.close_socket()
        self.create_socket()
        self.socket_monitor.monitor(socket=self.socket)
        if self.secure_socket:
            self.setup_secure_socket()

        self.setup_polling()

        self.set_socket_options()

        self.connect_socket()

    def close_socket(self) -> None:
        self.socket_monitor.unregister_socket_from_poller(socket=self.socket)

        if self.socket:
            try:
                self.socket.setsockopt(zmq.LINGER, 0)
                self.socket.close()
            except:
                pass

        if self.pollin:
            try:
                self.pollin.unregister(self.socket)
            except:
                pass

    async def stop(self) -> None:
        self.log('info', 'Stopping.')

        if self.socket_monitor.running:
            await self.socket_monitor.stop()

        if self.running:
            self.close_socket()

        self.running = False



