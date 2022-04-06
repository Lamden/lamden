from time import sleep
import zmq
import threading

from lamden.logger.base import get_logger
from zmq.auth.thread import ThreadAuthenticator
from lamden.crypto import wallet
from lamden.crypto.z85 import z85_key


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


class Router(threading.Thread):
    def __init__(self, router_wallet: wallet, get_all_peers, callback = None, logger=None):
        threading.Thread.__init__(self)
        self.log = logger or get_logger('ROUTER')
        self.ctx = zmq.Context()
        self.socket = None
        self.address = None
        self.wallet = router_wallet
        self.running = False
        self.paused = False # For testing
        self.cred_provider = CredentialsProvider(get_all_peers=get_all_peers, logger=self.log)
        self.callback = callback

    def __del__(self):
        print(f'[{self.log.name}][ROUTER] Destroyed')
        self.log.info(f'[ROUTER] Destroyed')

    @property
    def is_paused(self):
        return self.paused

    def run(self):
        print(f'[{self.log.name}][ROUTER] Starting on: ' + self.address)
        self.log.info('[ROUTER] Starting on: ' + self.address)

        # Start an authenticator for this context.
        self.socket = self.ctx.socket(zmq.ROUTER)

        auth = ThreadAuthenticator(self.ctx)
        auth.start()
        auth.configure_curve_callback(domain="*", credentials_provider=self.cred_provider)

        self.socket.curve_secretkey = self.wallet.curve_sk
        self.socket.curve_publickey = self.wallet.curve_vk
        self.socket.curve_server = True  # must come before bind

        self.socket.bind(self.address)

        # Create a poller to monitor if there is any
        poll = zmq.Poller()
        poll.register(self.socket, zmq.POLLIN)
        self.poll_time = 500

        self.running = True

        while self.running:
            if self.is_paused:
                sleep(0.5)
            else:
                try:
                    sockets = dict(poll.poll(self.poll_time))
                    # print(sockets[self.socket])
                    if self.socket in sockets:
                        ident, empty, msg = self.socket.recv_multipart()

                        print(f'[{self.log.name}][ROUTER] received: {ident}] {msg}')
                        self.log.info(f'[ROUTER] {ident} {msg}')

                        # print('Router received %s from %s' % (msg, ident))
                        if self.callback is not None:
                            self.callback(self, ident, msg)

                except zmq.ZMQError as e:
                    if e.errno == zmq.ETERM: # Interrupted
                        break

                    if e.errno == 38: # "Socket operation on non-socket"
                        print (e.errno)
                        self.stop()
                        return
                    raise

        self.socket.close()

    def send_msg(self, ident: str, msg):
        self.socket.send_multipart([ident, b'', msg])

    def pause(self):
        self.paused = True

    def unpause(self):
        self.paused = False

    def stop(self):
        if self.running:
            print(f'[{self.log.name}][ROUTER] Stopping.')
            self.log.info(f'[ROUTER] Stopping.')
            self.running = False
