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

    def __init__(self, server_vk=None, wallet=None, logger=None):
        self.log = logger or get_logger('REQUEST')

        self.ctx = zmq.asyncio.Context().instance()

        self.msg = ''

        self.running = True

        self.wallet = wallet or Wallet()
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
        return self.wallet.verifying_key

    @property
    def socket_is_bound(self):
        try:
            return len(self.socket.LAST_ENDPOINT) > 0
        except AttributeError:
            return False

    def create_socket(self):
        self.socket = self.ctx.socket(zmq.REQ)
        self.socket.setsockopt(zmq.LINGER, 100)

    def setup_secure_socket(self):
        if not self.secure_socket:
            raise AttributeError("Provided server_vk for a secure socket connection.")

        self.socket.curve_secretkey = self.wallet.curve_sk
        self.socket.curve_publickey = self.wallet.curve_vk
        self.socket.curve_serverkey = self.server_vk
        self.socket.identity = encode(self.id).encode()

    def setup_polling(self):
        self.pollin = zmq.Poller()
        self.pollin.register(self.socket, zmq.POLLIN)

    def connect_socket(self, address):
        self.socket.connect(address)

    def send_string(self, str_msg):
        if not self.socket:
            raise AttributeError("Socket has not been created.")

        if not self.socket_is_bound:
            raise AttributeError("Socket is not bound to an address.")

        self.socket.send_string(str_msg)

    def message_waiting(self, poll_time):
        return self.socket in dict(self.pollin.poll(poll_time))

    async def send(self, to_address, msg, timeout: int = 500, retries: int = 3) -> Result:
        self.log.info("[REQUEST] STARTING FOR PEER: " + to_address)
        error = None
        connection_attempts = 0

        while connection_attempts < retries:
            print(f'[REQUEST] Attempt {connection_attempts + 1}/{retries} to {to_address}; sending {msg}')
            self.log.info(f'[REQUEST] Attempt {connection_attempts + 1}/{retries} to {to_address}; sending {msg}')

            if not self.running:
                break

            try:
                self.create_socket()

                if self.secure_socket:
                    self.setup_secure_socket()

                self.setup_polling()
                self.connect_socket(address=to_address)

                self.send_string(str_msg=msg)

                if self.message_waiting(poll_time=timeout):
                    response = await self.socket.recv()

                    self.log.info(' %s received: %s' % (self.id, response))
                    print(f'[{self.log.name}] %s received: %s' % (self.id, response))

                    return Result(success=True, response=response)

                else:
                    self.log.info(f'[REQUEST] No response from {to_address} in poll time.')
                    print(f'[{self.log.name}] No response from {to_address} in poll time.')

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

            except Exception as err:
                self.log.error(f'[REQUEST] {err}')
                print(f'[{self.log.name}] {err}')
                error = str(err)

            connection_attempts += 1

        if not error:
            error = f'Request Socket Error: Failed to receive response after {retries} attempts each waiting {timeout}ms'

        return Result(success=False, error=error)


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


