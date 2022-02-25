import traceback

import zmq
import threading
from random import randint, random
import os
import logging
from zmq.auth.thread import ThreadAuthenticator
from lamden.crypto import wallet


class CredentialsProvider(object):

    def __init__(self, public_keys):
        print('init CredentialsProvider: ' + str(public_keys))
        self.public_keys = public_keys
        self.denied = []

    def add_key(self, new_key):
        print(f'adding key {new_key}')
        if new_key not in self.public_keys:
            self.public_keys.append(new_key)

    def remove_key(self, key_to_remove):
        if key_to_remove in self.public_keys:
            self.public_keys.remove(key_to_remove)

    def callback(self, domain, key):
        print(f'CredentialsProvider: checking auth for key: {key}')
        valid = key in self.public_keys
        if valid:
            logging.info('Authorizing: {0}, {1}'.format(domain, key))
            return True
        else:
            if key not in self.denied:
                self.denied.append(key)
            print('NOT Authorizing: {0}, {1}'.format(domain, key))
            logging.warning('NOT Authorizing: {0}, {1}'.format(domain, key))
            return False


class Router(threading.Thread):
    def __init__(self, address, router_wallet: wallet, public_keys=[], callback = None):
        threading.Thread.__init__(self)
        self.ctx = zmq.Context()
        self.socket = None
        self.address = address
        self.wallet = router_wallet
        self.publicKeys = public_keys
        self.running = False
        print('Router public keys: ' + str(self.publicKeys) + "address: " + address)
        self.cred_provider = CredentialsProvider(self.publicKeys)
        self.callback = callback
        self.msg_queue = []

    def __del__(self):
        print('router destroyed')

    def run(self):
        # print('router starting on: ' + self.address)

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

        self.running = True



        while self.running:
            try:
                sockets = dict(poll.poll(100))
                if self.socket in sockets:
                    ident, msg = self.socket.recv_multipart()
                    print('Router received %s from %s' % (msg, ident))
                    if self.callback is not None:
                        print('Router triggering callback')
                        self.callback(ident, msg)
                # if(len(self.msg_queue) > 0):
                #     self.socket.send_multipart(self.msg_queue.pop(0), flags=zmq.NOBLOCK)

            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    break  # Interrupted
                else:
                    raise
            except:
                print('router exception')
                traceback.print_exc()

        self.socket.close()
        # self.ctx.term()
        # print("router finished")

    def send_msg(self, ident: str, msg: str):
        try:
            print(f'router send message to {ident}: {msg}')
            self.socket.send_multipart([ident, msg], flags=zmq.NOBLOCK)
            # self.msg_queue.append([ident, msg])
        except:
            print('router exception')
            traceback.print_exc()


    def stop(self):
        print('stopping router')
        self.running = False
