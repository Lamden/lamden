import asyncio
import os
import pathlib

import zmq
import threading

from lamden.crypto.wallet import Wallet
from lamden.logger.base import get_logger
from lamden.nodes.filequeue import FileQueue, STORAGE_HOME
from zmq import __init__, ZMQBaseError
from zmq.auth import load_certificate
from zmq.auth.thread import ThreadAuthenticator
from lamden.crypto import wallet
from lamden.crypto.z85 import z85_key


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


DEFAULT_DIR = pathlib.Path.home() / CERT_DIR


async def secure_request(msg: dict, service: str, wallet: Wallet, vk: str, ip: str, ctx: zmq.asyncio.Context,
                         linger=500, timeout=1000, cert_dir=DEFAULT_DIR):
    #if wallet.verifying_key == vk:
    #    return

    socket = ctx.socket(zmq.DEALER)
    socket.setsockopt(zmq.LINGER, linger)
    socket.setsockopt(zmq.TCP_KEEPALIVE, 1)

    socket.curve_secretkey = wallet.curve_sk
    socket.curve_publickey = wallet.curve_vk

    filename = str(cert_dir / f'{vk}.key')
    if not os.path.exists(filename):
        return None

    server_pub, _ = load_certificate(filename)

    socket.curve_serverkey = server_pub

    try:
        socket.connect(ip)
    except ZMQBaseError:
        logger.debug(f'Could not connect to {ip}')
        socket.close()
        return None

    message = build_message(service=service, message=msg)

    payload = encode(message).encode()

    await socket.send(payload)

    event = await socket.poll(timeout=timeout, flags=zmq.POLLIN)
    msg = None
    if event:
        #logger.debug(f'Message received on {ip}')
        response = await socket.recv()

        msg = decode(response)

    socket.close()

    return msg


class MessageProcessor:
    def __init__(self):
        self.queues = {}
        self.services = {}
        self.is_running = False

    def add_service(self, name: str, processor: Processor):
        self.services[name] = processor
        self.queues[name] = FileQueue(root=STORAGE_HOME.joinpath(name))

    def check_inbox(self):
        for k, v in self.queues.items():
            try:
                item = v.pop(0)
                self.services[k].process_message(item)
            except IndexError:
                pass

    async def loop(self):
        self.is_running = True

        while self.is_running:
            self.check_inbox()
            await asyncio.sleep(0)


CERT_DIR = 'cilsocks'
logger = get_logger('Router')
OK = {
    'response': 'ok'
}


def build_message(service, message):
    return {
        'service': service,
        'msg': message
    }


class Processor:
    async def process_message(self, msg):
        raise NotImplementedError


class QueueProcessor(Processor):
    def __init__(self):
        self.q = []

    async def process_message(self, msg):
        self.q.append(msg)