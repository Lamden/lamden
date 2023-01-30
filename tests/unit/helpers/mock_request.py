import zmq
import zmq.asyncio
import asyncio
import unittest
import time

from lamden.logger.base import get_logger
from lamden.crypto.wallet import Wallet
from contracting.db.encoder import encode


class Result:
    def __init__(self, success, response=None, error=None):
        self.success = success
        self.response = response
        self.error = error

class MockRequest():
    con_failed = 'con_failed'

    def __init__(self, server_curve_vk: int = None, local_wallet: Wallet = None, logger=None, ctx: zmq.Context = None):
        self.log = logger or get_logger('REQUEST')

        self.ctx = ctx or zmq.asyncio.Context()

        self.msg = ''

        self.running = True

        self.local_wallet = local_wallet or Wallet()
        self.server_curve_vk = server_curve_vk

        self.socket = None
        self.pollin = None

        self.response = ''
        self.result = False

    @property
    def is_running(self) -> bool:
        return self.running

    @property
    def secure_socket(self) -> bool:
        return self.server_curve_vk is not None

    @property
    def id(self) -> str:
        return self.local_wallet.verifying_key

    @property
    def curve_vk(self) -> str:
        return self.local_wallet.curve_vk

    def socket_is_bound(self, socket) -> bool:
        try:
            return len(socket.LAST_ENDPOINT) > 0
        except AttributeError:
            return False

    def create_socket(self) -> zmq.Socket:
        socket = self.ctx.socket(zmq.REQ)
        return socket

    def setup_secure_socket(self, socket: zmq.Socket) -> None:
        if not self.secure_socket:
            raise AttributeError("Provided server_vk for a secure socket connection.")

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

    def send_string(self, msg_str: str, socket: zmq.Socket) -> None:
        if not socket:
            raise AttributeError("Socket has not been created.")

        if not self.socket_is_bound(socket=socket):
            raise AttributeError("Socket is not bound to an address.")

        if not isinstance(msg_str, str):
            raise TypeError("Message Must be string.")

        socket.send_string(msg_str)

    async def message_waiting(self, poll_time: int, socket: zmq.Socket = None, pollin: zmq.Poller = None) -> bool:
        sockets = await pollin.poll(poll_time)
        return socket in dict(sockets)

    async def send(self, to_address: str, msg_str: str, timeout_ms: int = 500, retries: int = 1) -> Result:
        self.log.info("[REQUEST] STARTING FOR PEER: " + to_address)
        error = None
        connection_attempts = 0

        while connection_attempts < retries:
            print(f'[REQUEST] Attempt {connection_attempts + 1}/{retries} to {to_address}; sending {msg_str}')
            self.log.info(f'[REQUEST] Attempt {connection_attempts + 1}/{retries} to {to_address}; sending {msg_str}')

            if not self.running:
                break

            try:
                socket = self.create_socket()

                if self.secure_socket:
                    self.setup_secure_socket(socket=socket)

                pollin = self.setup_polling(socket=socket)
                self.connect_socket(socket=socket, address=to_address)

                self.send_string(msg_str=msg_str, socket=socket)

                if await self.message_waiting(socket=socket, pollin=pollin, poll_time=timeout_ms):
                    response = await socket.recv()

                    self.log.info(' %s received: %s' % (self.id, response))
                    print(f'[{self.log.name}] %s received: %s' % (self.id, response))

                    self.close_socket(socket=socket)
                    return Result(success=True, response=response)

                else:
                    self.log.info(f'[REQUEST] No response from {to_address} in poll time.')
                    print(f'[{self.log.name}] No response from {to_address} in poll time.')

                self.close_socket(socket=socket)

            except zmq.ZMQError as err:
                if err.errno == zmq.ETERM:
                    self.log.info('[REQUEST] Interrupted')
                    print(f'[{self.log.name}] Interrupted')
                    error = err.strerror
                    break  # Interrupted

                else:
                    self.log.info('[REQUEST] error: ' + err.strerror)
                    print(f'[{self.log.name}] error: ' + err.strerror)
                    error = err.strerror

            except TypeError as err:
                self.log.error(f'[REQUEST] {err}')
                print(f'[{self.log.name}] {err}')
                error = str(err)
                break

            except Exception as err:
                self.log.error(f'[REQUEST] {err}')
                print(f'[{self.log.name}] {err}')
                error = str(err)

            connection_attempts += 1

        if not error:
            error = f'Request Socket Error: Failed to receive response after {retries} attempts each waiting {timeout_ms}ms'

        self.close_socket(socket=socket)
        return Result(success=False, error=error)

    def close_socket(self, socket: zmq.Socket) -> None:
        if socket:
            try:
                socket.close()
            except:
                pass

    def stop(self) -> None:
        self.running = False
        self.log.info('[REQUEST] Stopping.')
        print(f'[{self.log.name}] Stopping.')

class TestMockRequest(unittest.TestCase):
    def setUp(self) -> None:
        self.wallet = Wallet()
        self.server_wallet = Wallet()

        self.request = MockRequest(
            local_wallet=self.wallet,
            server_curve_vk=self.server_wallet.curve_vk
        )

    def tearDown(self) -> None:
        self.request.stop()

    def test_can_create_instance(self):
        self.assertIsInstance(self.request, MockRequest)

    def test_METHOD_stop__raises_no_erros(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.request.send(to_address="tcp://127.0.0.1:19000", msg_str="Test", timeout_ms=500))

        try:
            self.request.stop()
        except:
            self.fail("Stop should not raise erros.")


        self.assertFalse(self.request.running)

    def test_METHOD_send_string__sends_for_timeout_ms(self):
        start_time = time.time()
        timeout_ms = 2000
        timeout_sec = timeout_ms / 1000

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.request.send(to_address="tcp://127.0.0.1:19000", msg_str="Test", timeout_ms=2000))

        finish_time = time.time()

        run_time = finish_time - start_time

        self.assertTrue(run_time > timeout_sec)
