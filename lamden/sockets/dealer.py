from time import sleep
import zmq
import threading
from random import randint, random
import os
import logging
from zmq.auth.thread import ThreadAuthenticator
from zmq.sugar.constants import NOBLOCK
from lamden.crypto import wallet
from contracting.db.encoder import encode


class Dealer(threading.Thread):

    msg_hello = 'hello'
    con_failed = 'con_failed'

    def __init__(self, _id, _address, server_vk, wallet: wallet, ctx, _callback = None):
        self.ctx = zmq.Context()
        self.id = _id
        self.address = _address
        self.callback = _callback
        threading.Thread.__init__ (self)
        self.connected = False
        self.server_vk = server_vk
        self.wallet = wallet
        self.socket = self.ctx.socket(zmq.DEALER)
        self.socket.curve_secretkey = self.wallet.curve_sk
        self.socket.curve_publickey = self.wallet.curve_vk
        self.socket.curve_serverkey = self.server_vk
        self.socket.identity = encode(self.id).encode()
        self.socket.setsockopt(zmq.LINGER, 500)
        self.running = False

    def run(self):
        # Get an instance of the ZMQ Context

        self.running = True

        logging.info("DEALER STARTING ON: " + self.address)

        self.socket.connect(self.address)

        # Create a poller to monitor if there is any
        poll = zmq.Poller()
        poll.register(self.socket, zmq.POLLIN)

        # Send message to server to let it know there was a connection
        self.socket.send_string(Dealer.msg_hello, flags=zmq.NOBLOCK)

        connected = False
        connection_attempts = 0
        max_attempts = 50000
        poll_time = 1000

        while self.running:
            try:                
                sockets = dict(poll.poll(poll_time))
                if self.socket in sockets:   
                    # print('self.socket in sockets: True')
                    msg = self.socket.recv()
                    connected = True
                    logging.info('Dealer %s received: %s' % (self.id, msg))
                    if self.callback:
                        self.callback(msg)
                else:
                    if not connected:
                        logging.info('failed to received response, attempting to reconnect')
                        self.socket.disconnect(self.address)
                        connection_attempts += 1
                        if connection_attempts >= max_attempts:
                            self.running = False
                            self.callback(Dealer.con_failed)
                            break
                        self.socket.connect(self.address)
                        self.socket.send_string(Dealer.msg_hello, flags=zmq.NOBLOCK)
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    logging.info('Interrupted')
                    break           # Interrupted
                else:
                    logging.info('error: ' + e.strerror)
                    sleep(1)
        # print("dealer finished")
        self.socket.close()

    def send_msg(self, msg):
        self.socket.send_string(msg)

    def stop(self):
        # print('stopping dealer: ' + self.id)
        self.running = False
