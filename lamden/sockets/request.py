import time
from time import sleep
import zmq
import threading
from lamden.logger.base import get_logger

from lamden.crypto.wallet import Wallet
from contracting.db.encoder import encode
import threading

class Result:
    def __init__(self, success, response=None, error=None):
        self.success = success
        self.response = response
        self.error = error

class Request(threading.Thread):
    con_failed = 'con_failed'

    def __init__(self, server_vk=None, wallet=None, ctx=None, logger=None):
        self.log = logger or get_logger('REQUEST')

        self.ctx = zmq.Context()

        threading.Thread.__init__ (self)
        # self.threadLock = threading.Lock()

        self.msg = ''

        self.running = True

        self.wallet = wallet or Wallet()
        self.server_vk = server_vk

        self.socket = None
        self.poll = None

        self.response = ''
        self.result = False

    @property
    def secure_socket(self):
        return self.server_vk is not None

    @property
    def id(self):
        return self.wallet.verifying_key

    def create_socket(self):
        self.socket = self.ctx.socket(zmq.REQ)

    def setup_secure_socket(self):
        if not self.secure_socket:
            raise AttributeError("Provided server_vk for a secure socket connection.")

        self.socket.curve_secretkey = self.wallet.curve_sk
        self.socket.curve_publickey = self.wallet.curve_vk
        self.socket.curve_serverkey = self.server_vk
        self.socket.identity = encode(self.id).encode()
        self.socket.setsockopt(zmq.LINGER, 100)

    def setup_polling(self):
        self.poll = zmq.Poller()
        self.poll.register(self.socket, zmq.POLLIN)

    def connect_socket(self, address):
        self.socket.connect(address)

    def send_sting(self, str_msg):
        self.socket.send_string(str_msg)

    def should_poll(self, poll_time):
        return self.socket in dict(self.poll.poll(poll_time))

    def send(self, to_address, msg, timeout: int = 500, retries: int = 3) -> Result:
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
                self.send_sting(str_msg=msg)

                if self.should_poll(poll_time=timeout):
                    response = self.socket.recv()

                    self.log.info(' %s received: %s' % (self.id, response))
                    print(f'[{self.log.name}] %s received: %s' % (self.id, response))

                    return Result(success=True, response=response)

                else:
                    print(f'no response in poll time {time.time()}')
                    connection_attempts += 1

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
                    connection_attempts += 1

            except Exception as err:
                self.log.error(f'[REQUEST] {err}')
                print(f'[{self.log.name}] {err}')
                connection_attempts += 1
                error = str(err)

        if not error:
            error = f'Request Socket Error: Failed to receive response after {retries} attempts each waiting {timeout}ms'

        return Result(success=False, error=error)


    def stop(self):
        self.running = False
        self.log.info('[REQUEST] Stopping.')
        print(f'[{self.log.name}] Stopping. {time.time()}')
        if self.socket:
            try:
                self.socket.close()
            except zmq.ZMQError as err:
                self.log.error(f'[REQUEST] Error Stopping: {err}')
                print(f'[{self.log.name}] Error Stopping: {err}')
                pass


