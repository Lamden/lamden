import json
from time import sleep
import zmq
import threading
from lamden.logger.base import get_logger

from lamden.crypto import wallet
from contracting.db.encoder import encode
import threading
import asyncio

class Result:
    def __init__(self, success, response):
        self.success = success
        self.response = response


class Request(threading.Thread):
    con_failed = 'con_failed'

    def __init__(self, _id, _address, server_vk, wallet: wallet, ctx=None, logger=None):

        self.log = logger or get_logger('REQUEST')

        self.ctx = zmq.Context()

        self.id = _id
        self.address = _address

        threading.Thread.__init__ (self)
        self.state = 0
        self.msg = ''

        self.connected = False
        self.server_vk = server_vk
        self.wallet = wallet
        self.threadLock = threading.Lock()
        self.connection_attempts = 0
        self.running = False
        self.socket = None
        self.max_attempts = 5
        self.poll_time = 250
        self.response = ''
        self.result = False

    def create_socket(self):
        self.socket = self.ctx.socket(zmq.REQ)
        self.socket.curve_secretkey = self.wallet.curve_sk
        self.socket.curve_publickey = self.wallet.curve_vk
        self.socket.curve_serverkey = self.server_vk
        self.socket.identity = encode(self.id).encode()
        self.socket.setsockopt(zmq.LINGER, 100)

    async def run(self):
        self.running = True
        self.log.info("[REQUEST] STARTING FOR PEER: " + self.address)

        while self.running:
            # print("request: I'm Running")
            if(self.state == 0):
                sleep(0.1)
            elif(self.state == 1):
                while self.connection_attempts < self.max_attempts and self.running:
                    self.log.info(f'[REQUEST] attempting to send msg: ' + self.msg)
                    print(f'[{self.log.name}][REQUEST] attempting to send msg: ' + self.msg)
                    self.create_socket()
                    try:
                        poll = zmq.Poller()
                        poll.register(self.socket, zmq.POLLIN)
                        self.socket.connect(self.address)
                        self.socket.send_string(self.msg)
                        sockets = dict(poll.poll(self.poll_time))
                        # self.log.info(sockets)
                        if self.socket in sockets:
                            msg = self.socket.recv()
                            self.log.info(' %s received: %s' % (self.id, msg))
                            print(f'[{self.log.name}] %s received: %s' % (self.id, msg))
                            self.response = msg
                            self.result = True
                            # if self.callback:
                            #     self.callback(True, msg)
                            self.state = 0
                            self.socket.close()
                            return
                        else:
                            print('no response in poll time')
                            self.connection_attempts += 1
                            self.socket.close()
                            sleep(0.5)
                    except zmq.ZMQError as e:
                        if e.errno == zmq.ETERM:
                            self.log.info('[REQUEST] Interrupted')
                            print(f'[{self.log.name}][REQUEST] Interrupted')
                            break           # Interrupted
                        else:
                            self.log.info('[DEALER] error: ' + e.strerror)
                            print(f'[{self.log.name}][REQUEST] error: ' + e.strerror)
                            sleep(1)
                            self.connection_attempts += 1
                            self.socket.close()
                            sleep(0.5)
                    except Exception as err:
                        self.log.error(f'[REQUEST] {err}')
                        print(f'[{self.log.name}][REQUEST] {err}')
                        self.connection_attempts += 1
                        self.socket.close()
                        sleep(0.5)
                self.response = f'Request Socket Error: Failed to receive response after {self.max_attempts} attempts each waiting {self.poll_time}'
                print(self.response)
                self.state = 0
                self.result = False
                # print("dealer finished")
                return

    def send_msg(self, msg, callback):
        # self.socket.send_string(msg)
        if(self.state is 0):
            self.msg = msg
            self.callback = callback
            self.connection_attempts = 0
            self.state = 1
            return True
        else:
            print('error already sending a message')
            return False

    def send_msg_await(self, msg, time_out: int, retries: int):
        self.result = False
        self.response = ''
        self.max_attempts = retries
        self.poll_time = time_out
        self.msg = msg
        self.connection_attempts = 0
        self.state = 1
        return self.send()
        # print(f'request {result}, {response}')
        # return {result, response}

    def send(self):
        self.running = True
        self.log.info("[REQUEST] STARTING FOR PEER: " + self.address)
        while self.connection_attempts < self.max_attempts and self.running:
            print('[REQUEST] attempting to send msg: ' + self.msg)
            self.create_socket()
            try:
                poll = zmq.Poller()
                poll.register(self.socket, zmq.POLLIN)
                self.socket.connect(self.address)
                self.socket.send_string(self.msg)
                sockets = dict(poll.poll(self.poll_time))
                # self.log.info(sockets)
                if self.socket in sockets:
                    msg = self.socket.recv()
                    self.log.info(' %s received: %s' % (self.id, msg))
                    print(f'[{self.log.name}] %s received: %s' % (self.id, msg))
                    # return {'successful': True, 'response': msg}
                    return Result(True, msg)
                    # self.response = msg
                    # self.result = True
                    self.state = 0
                    self.socket.close()
                    return
                else:
                    print('no response in poll time')
                    self.connection_attempts += 1
                    self.socket.close()
                    sleep(0.5)
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    self.log.info('[REQUEST] Interrupted')
                    print(f'[{self.log.name}][REQUEST] Interrupted')
                    break  # Interrupted
                else:
                    self.log.info('[REQUEST] error: ' + e.strerror)
                    print(f'[{self.log.name}][REQUEST] error: ' + e.strerror)
                    sleep(1)
                    self.connection_attempts += 1
                    self.socket.close()
                    sleep(0.5)
            except Exception as err:
                self.log.error(f'[REQUEST] {err}')
                print(f'[{self.log.name}][REQUEST] {err}')
                self.connection_attempts += 1
                self.socket.close()
                sleep(0.5)
        response = f'Request Socket Error: Failed to receive response after {self.max_attempts} attempts each waiting {self.poll_time}'
        print(response)
        self.state = 0
        return Result(False, response)

    def stop(self):
        if self.running:
            self.log.info('[REQUEST] Stopping.')
            print(f'[{self.log.name}][REQUEST] Stopping.')
            self.running = False
