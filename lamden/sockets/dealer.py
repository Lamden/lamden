import traceback
from datetime import datetime
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

    def __init__(self, _id, _address, server_vk, wallet: wallet, ctx=None, _callback = None):
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
        self.socket.identity = self.id.encode()
        self.socket.setsockopt(zmq.LINGER, 100)
        self.running = False

    def run(self):
        # Get an instance of the ZMQ Context

        self.running = True

        logging.info("DEALER STARTING ON: " + self.address)
        print(f'Dealer {self.wallet.verifying_key} connecting to router {self.address} : {self.server_vk}')

        self.socket.connect(self.address)

        # Create a poller to monitor if there is any
        poll = zmq.Poller()
        poll.register(self.socket, zmq.POLLIN)

        # Send message to server to let it know there was a connection
        self.send_msg(Dealer.msg_hello)

        connected = False
        connection_attempts = 0
        max_attempts = 5
        poll_time = 100

        while self.running:
            # print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ': ' + f'--DEALER-- {self.id} polling')
            try:
                sockets = dict(poll.poll(poll_time))
                # print('dealer poll done')
                if self.socket in sockets:
                    # event = self.socket.poll(timeout=100, flags=zmq.POLLIN)
                    # if(event):
                    # print('self.socket in sockets: True')
                    msg = self.socket.recv()
                    connected = True
                    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ': ' + 'Dealer %s received: %s' % (self.id, msg))
                    # logging.info('Dealer %s received: %s' % (self.id, msg))
                    if self.callback:
                        print('Dealer calling callback')
                        self.callback(msg)
                    print('dealer after callback')
                else:
                    if not connected:
                        print('Dealer failed to received response, attempting to reconnect')
                        logging.info('failed to received response, attempting to reconnect')
                        self.socket.disconnect(self.address)
                        connection_attempts += 1
                        if connection_attempts >= max_attempts:
                            self.running = False
                            self.callback(Dealer.con_failed)
                            break
                        self.socket.connect(self.address)
                        self.send_msg(Dealer.msg_hello)
                    else:
                        # print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ': '
                        #       + 'Dealer %s did not receive msg in polling period' % self.id)
                        # print('dealer sleep for 0.01')
                        sleep(0.01)
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    logging.info('Interrupted')
                    break           # Interrupted
                else:
                    logging.info('error: ' + e.strerror)
                    sleep(1)
            except:
                print('dealer exception')
                traceback.print_exc()

        print("dealer finished: " + self.id)
        self.socket.close()

    def send_msg(self, msg):
        try:
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ': ' + f'dealer {self.wallet.verifying_key} send_msg: ' + msg)
            self.socket.send_string(msg, flags=zmq.NOBLOCK)
        except:
            print('dealer send_msg exception')

    def stop(self):
        logging.info('dealer stop: ' + self.id)
        print('stopping dealer: ' + self.id)
        self.running = False
