import zmq, zmq.asyncio, asyncio, ujson, os, uuid, json, inspect
from cilantro.protocol.overlay.interface import OverlayInterface
from cilantro.constants.overlay_network import EVENT_URL, CMD_URL, CLIENT_SETUP_TIMEOUT
from cilantro.storage.vkbook import VKBook
from cilantro.logger.base import get_logger
from cilantro.protocol.overlay.event import Event
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


def reply(fn):
    def _reply(self, *args, **kwargs):
        id_frame = args[0]
        res = fn(self, *args[1:], **kwargs)
        self.cmd_sock.send_multipart([
            id_frame,
            json.dumps(res).encode()
        ])

    return _reply


def async_reply(fn):
    def _reply(self, *args, **kwargs):
        def _done(fut):
            self.cmd_sock.send_multipart([
                id_frame,
                json.dumps(fut.result()).encode()
            ])

        id_frame = args[0]
        fut = asyncio.ensure_future(fn(self, *args[1:], **kwargs))
        fut.add_done_callback(_done)

    return _reply


class OverlayServer(object):
    def __init__(self, sk, loop=None, ctx=None, start=True):
        self.log = get_logger('OverlayServer')

        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.ctx = ctx or zmq.asyncio.Context()

        self.evt_sock = self.ctx.socket(zmq.PUB)
        self.evt_sock.bind(EVENT_URL)
        self.cmd_sock = self.ctx.socket(zmq.ROUTER)
        self.cmd_sock.bind(CMD_URL)

        Event.set_evt_sock(self.evt_sock)

        self.interface = OverlayInterface(sk, loop=loop, ctx=ctx)
        self.interface.tasks.append(self.command_listener())

        if start:
            self.start()

    def start(self):
        self.interface.start()

    async def command_listener(self):
        self.log.info('Listening for overlay commands over {}'.format(CMD_URL))
        while True:
            msg = await self.cmd_sock.recv_multipart()
            self.log.debug('[Overlay] Received cmd (Proc={}): {}'.format(msg[0], msg[1:]))
            data = [b.decode() for b in msg[2:]]
            getattr(self, msg[1].decode())(msg[0], *data)

    @async_reply
    async def get_node_from_vk(self, event_id, vk, domain='*', secure='False'):
        # TODO perhaps return an event instead of throwing an error in production
        assert vk in VKBook.get_all(), "Attempted to look up VK {} that is not in VKBook {}".format(vk, VKBook.get_all())

        ip = await self.interface.lookup_ip(vk)
        if not ip:
            return {
                'event': 'not_found',
                'event_id': event_id,
                'vk': vk
            }

        authorized = await self.interface.authenticate(ip, vk, domain) \
            if secure == 'True' else True
        return {
            'event': 'got_ip' if authorized else 'unauthorized_ip',
            'event_id': event_id,
            'ip': ip,
            'vk': vk
        }

    @async_reply
    async def check_node_status(self, event_id, vk):
        # TODO perhaps return an event instead of throwing an error in production
        assert vk in VKBook.get_all(), "Attempted to look up VK {} that is not in VKBook {}".format(vk, VKBook.get_all())

        ip = await self.interface.lookup_ip(vk)
        if not ip:
            return {
                'event': 'node_offline',
                'event_id': event_id,
                'vk': vk
            }
        else:
            return {
                'event': 'node_online',
                'event_id': event_id,
                'ip': ip,
                'vk': vk
            }

    @reply
    def get_service_status(self, event_id):
        if self.interface.started:
            return {
                'event': 'service_status',
                'status': 'ready'
            }
        else:
            return {
                'event': 'service_status',
                'status': 'not_ready'
            }

    def teardown(self):
        try:
            self.evt_sock.close()
            self.cmd_sock.close()
            try:
                self.fut.set_result('done')
            except:
                self.fut.cancel()
            self.interface.teardown()
            self.log.notice('Overlay service stopped.')
        except:
            pass


class OverlayClient(object):
    def __init__(self, event_handler, loop=None, ctx=None, start=False):
        self.log = get_logger('OverlayClient')
        self.loop = loop or asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)
        self.ctx = ctx or zmq.asyncio.Context()
        self.cmd_sock = self.ctx.socket(socket_type=zmq.DEALER)
        self.cmd_sock.setsockopt(zmq.IDENTITY, str(os.getpid()).encode())
        self.cmd_sock.connect(CMD_URL)
        self.evt_sock = self.ctx.socket(socket_type=zmq.SUB)
        self.evt_sock.setsockopt(zmq.SUBSCRIBE, b"")
        self.evt_sock.connect(EVENT_URL)
        self.tasks = [
            self.event_listener(event_handler),
            self.reply_listener(event_handler),
        ]

        self._ready = False
        if start:
            self.start()

    def start(self):
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
    def get_node_from_vk(self, *args, **kwargs):
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
            event_handler(msg)

    async def reply_listener(self, event_handler):
        self.log.info("Listening for overlay replies over {}".format(CMD_URL))
        while True:
            msg = await self.cmd_sock.recv_multipart()
            self.log.info("OverlayClient received reply {}".format(msg))
            event = json.loads(msg[-1])
            if event.get('event') == 'service_status' and \
                    event.get('status') == 'ready':
                self._ready = True
            elif event.get('event') == 'service_status' and \
                    event.get('status') == 'not_ready':
                self.log.info("OverlayClient received not ready. Reissuing service status command ...")
                await asyncio.sleep(2)
                self.get_service_status()
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
