import zmq
import zmq.asyncio
import asyncio
import os
import uuid
import json
from cilantro_ee.constants.overlay_network import EVENT_URL, CMD_URL
from cilantro_ee.core.logger.base import get_logger

log = get_logger('Overlay.Client')
# Sends the following multipart message
# [Function name encoded and event ID encoded], [Args encoded if it can be encoded], [KWards encoded if they can be]
# Returns event ID.


def command(fn):
    def _command(self, *args, **kwargs):
        log.info('COMMAND RUN: {}'.format(fn.__name__.encode()))
        event_id = uuid.uuid4().hex
        self.cmd_sock.send_multipart(
            [fn.__name__.encode(), event_id.encode()] + \
            [arg.encode() if hasattr(arg, 'encode') else str(arg).encode() for arg in args] + \
            [kwargs[k].encode() if hasattr(kwargs[k], 'encode') else str(kwargs[k]).encode() for k in kwargs])
        return event_id

    return _command


# Test Overlay Client. Try publishing mock messages to the event socket

class OverlayClient:
    def __init__(self, reply_handler, event_handler, ctx, name=None):
        self.name = name or str(os.getpid())

        self.log = get_logger('Overlay.Client.{}'.format(name))
        self.loop = asyncio.get_event_loop()
        self.ctx = ctx

        self.cmd_sock = self.ctx.socket(socket_type=zmq.DEALER)
        self.cmd_sock.setsockopt(zmq.IDENTITY, self.name.encode())
        self.cmd_sock.connect(CMD_URL)

        self.evt_sock = self.ctx.socket(socket_type=zmq.SUB)
        self.evt_sock.setsockopt(zmq.SUBSCRIBE, b"")
        self.evt_sock.connect('tcp://127.0.0.1:10003')

        self.tasks = [
            self.reply_listener(reply_handler),
            self.event_listener(event_handler),
        ]

        self.running = False

    @command
    def ready(self, *args, **kwargs):
        # b'ready'
        pass

    def get_ip_from_vk(self, *args, **kwargs):
        # b'get_ip_from_vk
        event_id = uuid.uuid4().hex
        self.cmd_sock.send_multipart(
            [b'get_ip_from_vk', event_id.encode()] + \
            [arg.encode() if hasattr(arg, 'encode') else str(arg).encode() for arg in args] + \
            [kwargs[k].encode() if hasattr(kwargs[k], 'encode') else str(kwargs[k]).encode() for k in kwargs]
        )
        return event_id

    async def event_listener(self, event_handler):
        self.log.success('Listening for overlay events.')
        while self.running:
            msg = await self.evt_sock.recv()
            self.log.success("OverlayClient received event {}".format(msg))

            response = json.loads(msg.decode())

            if isinstance(response, dict):
                event_handler(response)

    async def reply_listener(self, reply_handler):
        self.log.success("Listening for overlay replies over {}".format(CMD_URL))
        while self.running:
            msg = await self.cmd_sock.recv_multipart()
            event = json.loads(msg[-1])
            self.log.success("OverlayClient received reply {} and event {}".format(msg, event))
            reply_handler(event)

    def teardown(self):
        self.cmd_sock.close()
        self.evt_sock.close()

    async def start(self):
        self.running = True
        asyncio.ensure_future(asyncio.gather(*self.tasks))
        log.info('Overlay Client started!')

    def stop(self):
        self.running = False
