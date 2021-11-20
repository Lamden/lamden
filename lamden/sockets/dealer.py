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
    
    def __init__(self, _id, _address, server_vk, wallet: wallet, ctx, _callback = None):
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.DEALER)
        self.id = _id
        self.address = _address
        self.callback = _callback
        threading.Thread.__init__ (self)
        self.connected = False
        self.server_vk = server_vk
        self.wallet = wallet
        self.running = False


    def run(self):
        # Get an instance of the ZMQ Context

        self.running = True

        self.socket.curve_secretkey = self.wallet.curve_sk
        self.socket.curve_publickey = self.wallet.curve_vk


        print('sever vk')
        self.socket.curve_serverkey = self.server_vk

        print('dealer id: ' + self.id)

        self.socket.identity = encode(self.id).encode()
        self.socket.setsockopt(zmq.LINGER, 500)
        print("Dealer run start: " + self.address)

        self.socket.connect(self.address)


        # Create a poller to monitor if there is any
        poll = zmq.Poller()
        poll.register(self.socket, zmq.POLLIN)

        # TODO: When sending a message then start the poller to listen for a response...

        self.socket.send_string('hello', flags=zmq.NOBLOCK)

        connected = False
        while self.running:
            try:                
                print('polling')
                sockets = dict(poll.poll(1000))
                # print(sockets[self.socket])
                if self.socket in sockets:   
                    print('self.socket in sockets: True')                     
                    msg = self.socket.recv()
                    connected = True
                    # print('Dealer %s received: %s' % (self.id, msg))
                    if (self.callback):
                        self.callback(self.address, msg)
                else:
                    if not connected:
                        sleep(1)   
                        print('attempting to connect')              
                        self.socket.disconnect(self.address)
                        self.socket.connect(self.address)
                        self.socket.send_string('hello', flags=zmq.NOBLOCK)
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    print('Interrupted')
                    break           # Interrupted
                else:
                    print('error: ' + e.strerror)
                    sleep(1)

        
    def sendMsg(self, msg):
        self.socket.send_string(msg)

    def stop(self):
        print('stopping dealer: ' + self.id)
        self.running = False
        self.socket.disconnect(self.address)
        self.socket.close()
        self.ctx.term()
