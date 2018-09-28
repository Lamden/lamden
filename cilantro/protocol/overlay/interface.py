import zmq, zmq.asyncio, asyncio, ujson, os, uuid
from cilantro.protocol.overlay.dht import DHT
from cilantro.constants.overlay_network import ALPHA, KSIZE, MAX_PEERS, CLIENT_SETUP_TIMEOUT
from cilantro.storage.db import VKBook
from cilantro.logger.base import get_logger
from collections import deque
import json


EVENT_URL = 'ipc://overlay-event-ipc-sock-{}'.format(os.getenv('HOST_IP', 'test'))
CMD_URL = 'ipc://overlay-cmd-ipc-sock-{}'.format(os.getenv('HOST_IP', 'test'))


def command(fn):
    def _command(self, *args, **kwargs):
        event_id = uuid.uuid4().hex
        self.cmd_sock.send_multipart(
            ['_{}'.format(fn.__name__).encode(), event_id.encode()] + \
            [arg.encode() for arg in args] + \
            [kwargs[k].encode() for k in kwargs])
        return event_id
    return _command


class OverlayServer(object):
    def __init__(self, sk, loop=None, block=True):
        self.log = get_logger(type(self).__name__)
        self._started = False

        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.ctx = zmq.asyncio.Context()

        self.evt_sock = self.ctx.socket(zmq.PUB)
        self.evt_sock.bind(EVENT_URL)
        self.cmd_sock = self.ctx.socket(zmq.ROUTER)
        self.cmd_sock.bind(CMD_URL)

        self.fut = asyncio.ensure_future(self.command_listener())

        self.discovery_mode = 'test' if os.getenv('TEST_NAME') else 'neighborhood'
        self.dht = DHT(sk=sk, mode=self.discovery_mode, loop=self.loop,
                       alpha=ALPHA, ksize=KSIZE, event_sock=self.evt_sock,
                       max_peers=MAX_PEERS, block=False, cmd_cli=False, wipe_certs=True)

        self._started = True
        self.evt_sock.send_json({
            'event': 'service_status',
            'status': 'ready'
        })

        if block:
            self.loop.run_forever()

    async def command_listener(self):
        self.log.info('Listening for overlay commands over {}'.format(CMD_URL))
        while True:
            msg = await self.cmd_sock.recv_multipart()
            self.log.debug('[Overlay] Received cmd (Proc={}): {}'.format(msg[0], msg[1:]))
            data = [b.decode() for b in msg[2:]]
            getattr(self, msg[1].decode())(msg[0], *data)

    def _get_node_from_vk(self, id_frame, event_id, vk: str, domain='*', timeout=10):
        async def coro():
            node = None
            if vk in VKBook.get_all():
                try:
                    node, cached = await asyncio.wait_for(self.dht.network.lookup_ip(vk, domain), timeout)
                except asyncio.TimeoutError:
                    self.log.notice('Did not find an ip for VK {} in {}s'.format(vk, timeout))

            if node:
                data = json.dumps({
                    'event': 'got_ip',
                    'event_id': event_id,
                    'public_key': node.public_key.decode(),
                    'ip': node.ip,
                    'vk': vk
                }).encode()
            else:
                data = json.dumps({
                    'event': 'not_found',
                    'event_id': event_id
                }).encode()

            self.log.debugv("OverlayServer replying to id {} with data {}".format(id_frame, data))
            self.cmd_sock.send_multipart([id_frame, data])

        asyncio.ensure_future(coro())

    def _get_service_status(self, id_frame, event_id):
        if self._started:
            data = json.dumps({
                'event': 'service_status',
                'status': 'ready'
            }).encode()
        else:
            data = json.dumps({
                'event': 'service_status',
                'status': 'not_ready'
            }).encode()

        self.cmd_sock.send_multipart([id_frame, data])

    def teardown(self):
        try:
            self._started = False
            self.evt_sock.close()
            self.cmd_sock.close()
            try: self.fut.set_result('done')
            except: self.fut.cancel()
            self.dht.cleanup()
            self.log.notice('Overlay service stopped.')
        except:
            pass


class OverlayClient(object):
    def __init__(self, event_handler, loop=None, ctx=None, block=False):
        self.log = get_logger(type(self).__name__)

        self.loop = loop or asyncio.get_event_loop()
        self.ctx = ctx or zmq.asyncio.Context.instance()

        self.cmd_sock = self.ctx.socket(socket_type=zmq.DEALER)
        self.cmd_sock.setsockopt(zmq.IDENTITY, str(os.getpid()).encode())
        self.cmd_sock.connect(CMD_URL)
        self.evt_sock = self.ctx.socket(socket_type=zmq.SUB)
        self.evt_sock.setsockopt(zmq.SUBSCRIBE, b"")
        self.evt_sock.connect(EVENT_URL)

        self.event_future = asyncio.ensure_future(self.event_listener(event_handler))
        self.reply_future = asyncio.ensure_future(self.reply_listener(event_handler))

        self._ready = False

        try:
            self.loop.run_until_complete(self.block_until_ready())
        except:
            msg = '\nOverlayServer is not ready after {}s...\n'.format(CLIENT_SETUP_TIMEOUT)
            self.log.fatal(msg)
            raise Exception(msg)

        if block:
            self.loop.run_forever()

    async def block_until_ready(self):
        async def wait_until_ready():
            while not self._ready:
                await asyncio.sleep(0.5)

        self.get_service_status()
        await asyncio.wait_for(wait_until_ready(), CLIENT_SETUP_TIMEOUT)

    @command
    def get_node_from_vk(self, *args, **kwargs): pass

    @command
    def get_service_status(self, *args, **kwargs): pass

    async def event_listener(self, event_handler):
        self.log.info('Listening for overlay events over {}'.format(EVENT_URL))
        while True:
            msg = await self.evt_sock.recv_json()
            self.log.spam("OverlayClient received event {}".format(msg))
            if msg.get('event') == 'service_status' and msg.get('status') == 'ready':
                self._ready = True
            event_handler(msg)

    async def reply_listener(self, event_handler):
        self.log.info("Listening for overlay replies over {}".format(CMD_URL))
        while True:
            msg = await self.cmd_sock.recv_multipart()
            self.log.spam("OverlayClient received event {}".format(msg))
            event = json.loads(msg[-1])
            if event.get('event') == 'service_status' and event.get('status') == 'ready':
                self._ready = True
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
