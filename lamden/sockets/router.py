import threading

import zmq
from lamden.crypto import wallet
from lamden.crypto.z85 import z85_key
from lamden.logger.base import get_logger
from zmq.auth.thread import ThreadAuthenticator


class CredentialsProvider(object):

    def __init__(self, get_all_peers, logger=None):
        # print('init CredentialsProvider')
        self.log = logger or get_logger("ROUTER")
        self.get_all_peers = get_all_peers
        self.denied = []

    @property
    def approved_nodes(self):
        return [z85_key(vk) for vk in self.get_all_peers()]

    def add_key(self, new_key):
        # print(f'adding key {new_key}')
        if new_key not in self.public_keys:
            self.public_keys.append(new_key)

    def remove_key(self, key_to_remove):
        if key_to_remove in self.public_keys:
            self.public_keys.remove(key_to_remove)

    def callback(self, domain, key):
        valid = key in self.approved_nodes
        if valid:
            print(f'[{self.log.name}][ROUTER] Authorizing: {domain}, {key}')
            self.log.info(f'[ROUTER] Authorizing: {domain}, {key}')

            return True
        else:
            if key not in self.denied:
                self.denied.append(key)
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
        self.cred_provider = CredentialsProvider(get_all_peers=get_all_peers, logger=self.log)
        self.callback = callback

    def __del__(self):
        print(f'[{self.log.name}][ROUTER] Destroyed')
        self.log.info(f'[ROUTER] Destroyed')

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

    def stop(self):
        if self.running:
            print(f'[{self.log.name}][ROUTER] Stopping.')
            self.log.info(f'[ROUTER] Stopping.')
            self.running = False
            self.socket.close()

