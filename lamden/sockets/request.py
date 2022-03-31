import zmq
import zmq.asyncio
from lamden.logger.base import get_logger
from lamden.crypto.wallet import Wallet
from contracting.db.encoder import encode


class Result:
    def __init__(self, success, response=None, error=None):
        self.success = success
        self.response = response
        self.error = error

class Request():
    con_failed = 'con_failed'

    def __init__(self, server_vk=None, local_wallet=None, logger=None):
        self.log = logger or get_logger('REQUEST')

        self.ctx = zmq.asyncio.Context().instance()

        self.msg = ''

        self.running = True

        self.local_wallet = local_wallet or Wallet()
        self.server_vk = server_vk

        self.socket = None
        self.pollin = None

        self.response = ''
        self.result = False

    @property
    def is_running(self):
        return self.running

    @property
    def secure_socket(self):
        return self.server_vk is not None

    @property
    def id(self):
        return self.local_wallet.verifying_key

    def socket_is_bound(self, socket):
        try:
            return len(socket.LAST_ENDPOINT) > 0
        except AttributeError:
            return False

    def create_socket(self):
        socket = self.ctx.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 100)

        return socket

    def setup_secure_socket(self, socket):
        if not self.secure_socket:
            raise AttributeError("Provided server_vk for a secure socket connection.")

        socket.curve_secretkey = self.local_wallet.curve_sk
        socket.curve_publickey = self.local_wallet.curve_vk
        socket.curve_serverkey = self.server_vk
        socket.identity = encode(self.id).encode()

    def setup_polling(self, socket=None):
        pollin = zmq.Poller()
        pollin.register(socket, zmq.POLLIN)
        return pollin

    def connect_socket(self, address, socket):
        socket.connect(address)

    def send_string(self, str_msg, socket):
        if not socket:
            raise AttributeError("Socket has not been created.")

        if not self.socket_is_bound(socket=socket):
            raise AttributeError("Socket is not bound to an address.")

        if not isinstance(str_msg, str):
            raise TypeError("Message Must be string.")

        socket.send_string(str_msg)

    def message_waiting(self, poll_time, socket=None, pollin=None):
        return socket in dict(pollin.poll(poll_time))

    async def send(self, to_address, str_msg, timeout: int = 500, retries: int = 3) -> Result:
        self.log.info("[REQUEST] STARTING FOR PEER: " + to_address)
        error = None
        connection_attempts = 0

        while connection_attempts < retries:
            print(f'[REQUEST] Attempt {connection_attempts + 1}/{retries} to {to_address}; sending {str_msg}')
            self.log.info(f'[REQUEST] Attempt {connection_attempts + 1}/{retries} to {to_address}; sending {str_msg}')

            if not self.running:
                break

            try:
                socket = self.create_socket()

                if self.secure_socket:
                    self.setup_secure_socket(socket=socket)

                pollin = self.setup_polling(socket=socket)
                self.connect_socket(socket=socket, address=to_address)

                self.send_string(str_msg=str_msg, socket=socket)

                if self.message_waiting(socket=socket, pollin=pollin, poll_time=timeout):
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
            error = f'Request Socket Error: Failed to receive response after {retries} attempts each waiting {timeout}ms'

        self.close_socket(socket=socket)
        return Result(success=False, error=error)

    def close_socket(self, socket):
        if socket:
            try:
                socket.close()
            except:
                pass

    def stop(self):
        self.running = False
        self.log.info('[REQUEST] Stopping.')
        print(f'[{self.log.name}] Stopping.')
        if self.socket:
            try:
                self.socket.close()
            except zmq.ZMQError as err:
                self.log.error(f'[REQUEST] Error Stopping: {err}')
                print(f'[{self.log.name}] Error Stopping: {err}')
                pass


