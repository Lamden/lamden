import asyncio
from lamden.crypto.wallet import Wallet
import zmq
import zmq.asyncio
from contracting.db.encoder import encode, decode
from zmq.error import ZMQBaseError
from zmq.auth.certs import load_certificate
from lamden.logger.base import get_logger
import pathlib
import os
CERT_DIR = 'cilsocks'
DEFAULT_DIR = pathlib.Path.home() / CERT_DIR

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


'''
Router takes messages in the following format:
{
    'service': <name of service as string>,
    'msg': {
        <any JSON payload here>
    }
}
It then sends the msg to the registered 'processor' and returns
a message to the requester.
'''


class AsyncInbox:
    def __init__(self, socket_id, ctx: zmq.Context, wallet=None, linger=1000, poll_timeout=50):
        if socket_id.startswith('tcp'):
            _, _, port = socket_id.split(':')
            self.address = f'tcp://*:{port}'
        else:
            self.address = socket_id

        self.wallet = wallet

        self.ctx = ctx

        self.socket = None

        self.linger = linger
        self.poll_timeout = poll_timeout

        self.running = False

    async def serve(self):
        self.setup_socket()

        self.running = True

        while self.running:
            try:
                event = await self.socket.poll(timeout=self.poll_timeout, flags=zmq.POLLIN)
                if event:
                    _id, msg = await self.receive_message()
                    asyncio.ensure_future(self.handle_msg(_id, msg))
            except zmq.error.ZMQError:
                self.socket.close()
                self.setup_socket()

        self.socket.close()

    async def receive_message(self):
        _id = await self.socket.recv()
        msg = await self.socket.recv()

        return _id, msg

    async def handle_msg(self, _id, msg):
        await self.return_msg(_id, msg)

    async def return_msg(self, _id, msg):
        sent = False
        while not sent:
            try:
                await self.socket.send_multipart([_id, msg])
                sent = True
            except zmq.error.ZMQError:
                self.socket.close()
                self.setup_socket()

    def setup_socket(self):
        try:
            self.socket = self.ctx.socket(zmq.ROUTER)
            self.socket.setsockopt(zmq.LINGER, self.linger)
            self.socket.bind(self.address)
        except ZMQBaseError as e:
            logger.error(f'Setup socket error: {str(e)}')
            logger.error(self.address)

    def stop(self):
        self.running = False


class JSONAsyncInbox(AsyncInbox):
    def __init__(self, secure=False, *args, **kwargs):
        self.secure = secure

        super().__init__(*args, **kwargs)

    def setup_socket(self):
        self.socket = self.ctx.socket(zmq.ROUTER)

        if self.secure:
            self.socket.curve_secretkey = self.wallet.curve_sk
            self.socket.curve_publickey = self.wallet.curve_vk

            self.socket.curve_server = True

        self.socket.setsockopt(zmq.LINGER, self.linger)
        self.socket.bind(self.address)

    async def receive_message(self):
        _id = await self.socket.recv()
        msg = await self.socket.recv()

        return _id, decode(msg)

    async def return_msg(self, _id, msg):
        msg = encode(msg).encode()
        await super().return_msg(_id, msg)


class Router(JSONAsyncInbox):
    def __init__(self, debug=True, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.services = {}
        self.log = get_logger(self.address)
        self.log.propagate = debug

    async def handle_msg(self, _id, msg):
        service = msg.get('service')
        request = msg.get('msg')

        self.log.debug(f'Message recieved for: {service}.')

        if service is None:
            self.log.debug('No service found for message.')
            await super().return_msg(_id, OK)
            return

        if request is None:
            self.log.debug('No request found in message.')
            await super().return_msg(_id, OK)
            return

        processor = self.services.get(service)

        if processor is None:
            await super().return_msg(_id, OK)
            return

        response = await processor.process_message(request)

        if response is None:
            await super().return_msg(_id, OK)
            return

        await super().return_msg(_id, response)

    def add_service(self, name: str, processor: Processor):
        self.services[name] = processor


async def secure_send(msg: dict, service, wallet: Wallet, vk, ip, ctx: zmq.asyncio.Context, linger=500, cert_dir=DEFAULT_DIR):
    # JEFF: ?? Seems like the below code is there to prevent sending to yourself.
    # Does this not matter?
    #
    #if wallet.verifying_key == vk:
    #    return

    # JEFF: ?? Just want to see when we're doing secure_send

    socket = ctx.socket(zmq.DEALER)
    socket.setsockopt(zmq.LINGER, linger)
    # JEFF: Change keepalive to 5
    socket.setsockopt(zmq.TCP_KEEPALIVE, 5)

    socket.curve_secretkey = wallet.curve_sk
    socket.curve_publickey = wallet.curve_vk

    filename = str(cert_dir / f'{vk}.key')
    self.log('filename: ' + filename)
    if not os.path.exists(filename):
        self.log('KEY DOESNT EXIST')
        return None

    server_pub, _ = load_certificate(filename)

    socket.curve_serverkey = server_pub

    try:
        socket.connect(ip)
        self.log('Conneted To: ' + ip)
    except ZMQBaseError:
        self.log('Could not Connect to: ' + ip)
        socket.close()
        return None

    message = build_message(service=service, message=msg)
    self.log('message: ' + str(message))

    payload = encode(message).encode()
    self.log('payload: ' +  str(payload))

    await socket.send(payload, flags=zmq.NOBLOCK)
    socket.close()


async def secure_request(msg: dict, service: str, wallet: Wallet, vk: str, ip: str, ctx: zmq.asyncio.Context,
                         linger=500, timeout=1000, cert_dir=DEFAULT_DIR):
    #if wallet.verifying_key == vk:
    #    return

    # JEFF: ?? Just want to see when we're doing secure_request
    self.log('--- USING SECURE REQUEST ----')

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


async def secure_multicast(msg: dict, service, wallet: Wallet, peer_map: dict, ctx: zmq.asyncio.Context, linger=500, cert_dir=DEFAULT_DIR):
    coroutines = []
    for vk, ip in peer_map.items():
        self.log('vk:' + vk + ', ip:' + ip)
        coroutines.append(
            secure_send(msg=msg, service=service, cert_dir=cert_dir, wallet=wallet, vk=vk, ip=ip, ctx=ctx, linger=linger)
        )

    await asyncio.gather(*coroutines)
