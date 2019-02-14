import zmq, zmq.asyncio, asyncio, ujson, os, uuid, json, inspect
from cilantro.protocol.overlay.interface import OverlayInterface
from cilantro.constants.overlay_network import EVENT_URL, CMD_URL, CLIENT_SETUP_TIMEOUT
from cilantro.storage.vkbook import VKBook
from cilantro.logger.base import get_logger
from cilantro.protocol.overlay.event import Event
from collections import deque


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


class OverlayServer(OverlayInterface):
    def __init__(self, vk, loop=None, ctx=None, start=True):
        self.vk = vk
        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.ctx = ctx or zmq.asyncio.Context()

        self.log = get_logger('Overlay.Server')
        self.supported_methods = [func for func in dir(OverlayInterface) if callable(getattr(OverlayInterface, func)) and not func.startswith("__")]

        self.evt_sock = self.ctx.socket(zmq.PUB)
        self.evt_sock.bind(EVENT_URL)
        self.cmd_sock = self.ctx.socket(zmq.ROUTER)
        self.cmd_sock.bind(CMD_URL)

        # pass both evt_sock and cmd_sock ?
        self.network = Network(vk, self.loop, self.ctx)

        # do we pass event sock to network then
        Event.set_evt_sock(self.evt_sock)

        self.network.tasks.append(self.command_listener())

        if start:
            self.run()

    def run(self):
        self.network.start()

    async def command_listener(self):
        self.log.info('Listening for overlay commands over {}'.format(CMD_URL))
        while True:
            msg = await self.cmd_sock.recv_multipart()
            self.log.debug('[Overlay] Received cmd (Proc={}): {}'.format(msg[0], msg[1:]))
            data = [b.decode() for b in msg[2:]]

            # getattr(self, msg[1].decode())(msg[0], *data)
            func = msg[1].decode()
            if func in self.supported_methods:
                # getattr(self, func)(msg[0], *data)
                self.network.func(msg[0], *data)
            else:
                self.log.info('Listening for overlay commands over {}'.format(CMD_URL))
                # reply back with unsupported api error
           

    @async_reply
    async def get_node_from_vk(self, event_id, vk, domain='*', secure='False'):
        # TODO perhaps return an event instead of throwing an error in production
        if not vk in VKBook.get_all():
            return {
                'event': 'not_found',
                'event_id': event_id,
                'vk': vk
            }
        ip = await self.network.lookup_ip(vk)
        if not ip:
            return {
                'event': 'not_found',
                'event_id': event_id,
                'vk': vk
            }

        authorized = await self.network.authenticate(ip, vk, domain) \
                                      if secure == 'True' else True
        return {
            'event': 'got_ip' if authorized else 'unauthorized_ip',
            'event_id': event_id,
            'ip': ip,
            'vk': vk
        }

    @async_reply
    async def ping_node(self, event_id, ip):
        status = await self.network.ping_node(ip)
        if not status:
            return {
                'event': 'node_offline',
                'event_id': event_id,
                'ip': ip
            }
        else:
            return {
                'event': 'node_online',
                'event_id': event_id,
                'ip': ip
            }

    @reply
    def get_service_status(self, event_id):
        if self.network.ready:
            return {
                'event': 'service_status',
                'status': 'ready'
            }
        else:
            return {
                'event': 'service_status',
                'status': 'not_ready'
            }

    def set_new_node_tracking(self, *args, **kwargs):
        self.interface.track_new_nodes()

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

