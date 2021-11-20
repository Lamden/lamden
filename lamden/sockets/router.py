import zmq
import threading
from random import randint, random
import os
import logging
from zmq.auth.thread import ThreadAuthenticator
from lamden.crypto import wallet


class CredentialsProvider(object):

    def __init__(self, public_keys):
        # print('init CredentialsProvider')
        self.public_keys = public_keys

    def add_key(self, new_key):
        # print(f'adding key {new_key}')
        self.public_keys.append(new_key)

    def callback(self, domain, key):
        print(f'checking auth for key: {key}')
        valid = key in self.public_keys
        if valid:
            logging.info('Authorizing: {0}, {1}'.format(domain, key))
            return True
        else:
            logging.warning('NOT Authorizing: {0}, {1}'.format(domain, key))
            return False


class Router(threading.Thread):
    def __init__(self, address, wallet: wallet, public_keys, ctx):
        threading.Thread.__init__(self)
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.ROUTER)
        self.address = address
        self.wallet = wallet
        self.publicKeys = public_keys
        self.running = False
        self.cred_provider = CredentialsProvider(self.publicKeys)

    def run(self):
        self.running = True
        print('router starting on: ' + self.address)
        # Start an authenticator for this context.
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
        while self.running:
            try:
                sockets = dict(poll.poll(100))
                # print(sockets[self.socket])
                if self.socket in sockets:
                    ident, msg = self.socket.recv_multipart()
                    print('Router received %s from %s' % (msg, ident))
                    if msg == b'hello':
                        print('Router sending pub_info response to %s' % ident)
                        self.socket.send_multipart([ident, b'{"response":"pub_info", "address": "tcp://127.0.0.1:9999", '
                                                           b'"topics": [""]}'])
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    break  # Interrupted
                else:
                    raise

        self.socket.close()
        # self.ctx.term()
        print("router finished")

    def stop(self):
        print('stopping router')
        self.running = False

