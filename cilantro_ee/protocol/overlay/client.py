import zmq, zmq.asyncio, asyncio, ujson, os, uuid, json, inspect
from cilantro_ee.protocol.overlay.interface import OverlayInterface
from cilantro_ee.constants.overlay_network import EVENT_URL, CMD_URL, CLIENT_SETUP_TIMEOUT
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.logger.base import get_logger
from cilantro_ee.protocol.overlay.kademlia.event import Event
from collections import deque


def command(fn):
    def _command(self, *args, **kwargs):
        event_id = uuid.uuid4().hex
        self.cmd_sock.send_multipart(
            [fn.__name__.encode(), event_id.encode()] + \
            [arg.encode() if hasattr(arg, 'encode') else str(arg).encode() for arg in args] + \
            [kwargs[k].encode() if hasattr(kwargs[k], 'encode') else str(kwargs[k]).encode() for k in kwargs])
        return event_id

    return _command


class OverlayClient(OverlayInterface):
    def __init__(self, reply_handler, event_handler, ctx, name=None, start=False):
        self.name = name or str(os.getpid())
        self.log = get_logger('Overlay.Client.{}'.format(name))
        self.loop = asyncio.get_event_loop()
        self.ctx = ctx
        self.cmd_sock = self.ctx.socket(socket_type=zmq.DEALER)
        self.cmd_sock.setsockopt(zmq.IDENTITY, self.name.encode())
        self.cmd_sock.connect(CMD_URL)
        self.evt_sock = self.ctx.socket(socket_type=zmq.SUB)
        self.evt_sock.setsockopt(zmq.SUBSCRIBE, b"")
        self.evt_sock.connect(EVENT_URL)
        self.tasks = [
            self.reply_listener(reply_handler),
            self.event_listener(event_handler),
        ]

        self._ready = False
        if start:
            self.run()

    def run(self):
        try:
            asyncio.ensure_future(asyncio.gather(*self.tasks))
            self.loop.run_until_complete(self.block_until_ready())
        except:
            msg = '\nOverlayServer is not ready after {}s...\n'.format(CLIENT_SETUP_TIMEOUT)
            self.log.fatal(msg)
            raise Exception(msg)

    async def block_until_ready(self):
        async def wait_until_ready():
            while not self._ready:
                await asyncio.sleep(2)

        await asyncio.sleep(6)
        self.get_service_status()
        await asyncio.wait_for(wait_until_ready(), CLIENT_SETUP_TIMEOUT)

    @command
    def get_ip_from_vk(self, *args, **kwargs):
        pass

    @command
    def get_ip_and_handshake(self, *args, **kwargs):
        pass

    @command
    def handshake_with_ip(self, *args, **kwargs):
        pass

    @command
    def ping_ip(self, *args, **kwargs):
        pass

    @command
    def get_service_status(self, *args, **kwargs):
        pass

    async def event_listener(self, event_handler):
        self.log.info('Listening for overlay events over {}'.format(EVENT_URL))
        while True:
            msg = await self.evt_sock.recv_json()
            self.log.debug("OverlayClient received event {}".format(msg))
            if msg.get('event') == 'service_status' and msg.get('status') == 'ready':
                self._ready = True
            else:
                event_handler(msg)

    async def reply_listener(self, event_handler):
        self.log.debugv("Listening for overlay replies over {}".format(CMD_URL))
        while True:
            msg = await self.cmd_sock.recv_multipart()
            self.log.debug("OverlayClient received reply {}".format(msg))
            event = json.loads(msg[-1])
            if event.get('event') == 'service_status' and \
                    event.get('status') == 'ready':
                self._ready = True
            else:
                event_handler(event)

    def teardown(self):
        self.cmd_sock.close()
        self.evt_sock.close()
        try:
            for fut in (self.event_future, self.reply_future):
                fut.set_result('done')
        except:
            for fut in (self.event_future, self.reply_future):
                fut.cancel()
