import zmq, zmq.asyncio, asyncio, ujson, os, uuid, json, inspect
from cilantro_ee.protocol.overlay.interface import OverlayInterface
from cilantro_ee.constants.overlay_network import EVENT_URL, CMD_URL, CLIENT_SETUP_TIMEOUT
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.logger.base import get_logger
from cilantro_ee.protocol.overlay.kademlia.event import Event
from collections import deque
from cilantro_ee.protocol.comm import services
from cilantro_ee.protocol.overlay.kademlia.new_network import Network as NewNetwork

# Sends the following multipart message
# [Function name encoded and event ID encoded], [Args encoded if it can be encoded], [KWards encoded if they can be]
# Returns event ID.
def command(fn):
    def _command(self, *args, **kwargs):
        event_id = uuid.uuid4().hex
        self.cmd_sock.send_multipart(
            [fn.__name__.encode(), event_id.encode()] + \
            [arg.encode() if hasattr(arg, 'encode') else str(arg).encode() for arg in args] + \
            [kwargs[k].encode() if hasattr(kwargs[k], 'encode') else str(kwargs[k]).encode() for k in kwargs])
        return event_id

    return _command


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

    @command
    def ready(self, *args, **kwargs):
        # b'ready'
        pass

    @command
    def get_ip_from_vk(self, *args, **kwargs):
        # b'get_ip_from_vk
        self.log.success('GET IP FROM VK SHIT: {} {}'.format(args, kwargs))
        pass

    async def event_listener(self, event_handler):
        self.log.success('Listening for overlay events over {}'.format(EVENT_URL))
        while True:
            msg = await self.evt_sock.recv()
            self.log.success("OverlayClient received event {}".format(msg))
            response = json.loads(msg.decode())

            if isinstance(response, dict):
                event_handler(response)

    async def reply_listener(self, reply_handler):
        self.log.success("Listening for overlay replies over {}".format(CMD_URL))
        while True:
            msg = await self.cmd_sock.recv_multipart()
            event = json.loads(msg[-1])
            self.log.success("OverlayClient received reply {} and event {}".format(msg, event))
            reply_handler(event)

    def teardown(self):
        self.cmd_sock.close()
        self.evt_sock.close()


