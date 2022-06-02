import asyncio

import zmq
import zmq.asyncio
from lamden.logger.base import get_logger
from lamden.crypto.wallet import Wallet
from contracting.db.encoder import encode
from lamden.sockets.monitor import SocketMonitor

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
    def __init__(self, server_curve_vk: int = None, local_wallet: Wallet = None, ctx: zmq.Context = None,
                 local_ip: str = None):
        self.ctx = ctx or zmq.asyncio.Context().instance()
        self.msg = ''

        self.running = True


        self.local_ip = local_ip
        self.local_wallet = local_wallet or Wallet()
        self.server_curve_vk = server_curve_vk

        self.lock = Lock()

        self.socket_monitor = SocketMonitor(socket_type="REQUEST")
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
            print(f'[{self.local_ip}]{named_message}\n')
        else:
            named_message = message
            logger = get_logger(f'REQUEST')
            print(f'[REQUEST] {named_message}\n')

        if log_type == 'info':
            logger.info(named_message)
        if log_type == 'error':
            logger.error(named_message)
        if log_type == 'warning':
            logger.warning(named_message)

    def socket_is_bound(self, socket) -> bool:
        try:
            return len(socket.LAST_ENDPOINT) > 0
        except AttributeError:
            return False

    def create_socket(self) -> zmq.Socket:
        socket = self.ctx.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 500)
        socket.setsockopt(zmq.TCP_KEEPALIVE, 1)

        return socket

    def setup_secure_socket(self, socket: zmq.Socket) -> None:
        if not self.secure_socket:
            raise AttributeError("Provided server_curve_vk for a secure socket connection.")

        socket.curve_secretkey = self.local_wallet.curve_sk
        socket.curve_publickey = self.local_wallet.curve_vk
        socket.curve_serverkey = self.server_curve_vk
        socket.identity = encode(self.id).encode()

    def setup_polling(self, socket: zmq.Socket = None) -> zmq.Poller:
        pollin = zmq.asyncio.Poller()
        pollin.register(socket, zmq.POLLIN)
        return pollin

    def connect_socket(self, address: str, socket: zmq.Socket = None) -> None:
        socket.connect(address)

    def send_string(self, str_msg: str, socket: zmq.Socket) -> None:
        if not socket:
            raise AttributeError("Socket has not been created.")

        if not self.socket_is_bound(socket=socket):
            raise AttributeError("Socket is not bound to an address.")

        if not isinstance(str_msg, str):
            raise TypeError("Message Must be string.")

        return socket.send_string(str_msg)

    async def message_waiting(self, poll_time: int,  pollin: zmq.asyncio.Poller, socket: zmq.Socket,) -> bool:
        try:
            sockets = await pollin.poll(timeout=poll_time)
            return socket in dict(sockets)
        except Exception as err:
            self.log('error', err)
            return False

    async def send(self, to_address: str, str_msg: str, timeout: int = 2500, retries: int = 3) -> Result:
        async with self.lock:
            error = None
            connection_attempts = 0

            while connection_attempts < retries:
                self.log('info', f'Attempt {connection_attempts + 1}/{retries} to {to_address}; sending {str_msg}')

                if not self.running:
                    break

                try:
                    socket = self.create_socket()

                    self.socket_monitor.monitor(socket=socket)

                    if self.secure_socket:
                        self.setup_secure_socket(socket=socket)

                    pollin = self.setup_polling(socket=socket)
                    self.connect_socket(socket=socket, address=to_address)

                    tracking = self.send_string(str_msg=str_msg, socket=socket)

                    if isinstance(tracking, asyncio.Future):
                        await tracking
                        self.log('info', 'Message sent!')
                    else:
                        self.log('error', 'Message NOT sent!')

                    if await self.message_waiting(socket=socket, pollin=pollin, poll_time=timeout):
                        response = await socket.recv()

                        self.log('info', '%s received: %s' % (self.id, response))

                        self.close_socket(socket=socket, pollin=pollin)
                        return Result(success=True, response=response)

                    else:
                        self.log('warning', f'No response from {to_address} in poll time.')

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
                self.close_socket(socket=socket, pollin=pollin)
                await asyncio.sleep(0)

            if not error:
                error = f'Request Socket Error: Failed to receive response after {retries} attempts each waiting {timeout}ms'

            return Result(success=False, error=error)

    def close_socket(self, socket: zmq.Socket, pollin: zmq.asyncio.Poller) -> None:
        self.socket_monitor.unregister_socket_from_poller(socket=socket)

        if socket:
            try:
                socket.setsockopt(zmq.LINGER, 0)
                socket.close()
            except:
                pass

        if pollin:
            try:
                pollin.unregister(socket)
            except:
                pass

    async def stop(self) -> None:
        self.log('info', 'Stopping.')

        asyncio.ensure_future(self.socket_monitor.stop())

        await self.socket_monitor.stop()

        self.running = False


