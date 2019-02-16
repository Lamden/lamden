import zmq, zmq.asyncio, asyncio, ujson, os, uuid, json, inspect
from cilantro.utils.keys import Keys
from cilantro.protocol.overlay.interface import OverlayInterface
from cilantro.constants.overlay_network import EVENT_URL, CMD_URL, CLIENT_SETUP_TIMEOUT
from cilantro.storage.vkbook import VKBook
from cilantro.logger.base import get_logger
from cilantro.protocol.overlay.kademlia.event import Event
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
    def __init__(self, sk, ctx, start=True):
        self.sk = sk
        Keys.setup(sk_hex=self.sk)
        self.loop = asyncio.get_event_loop()
        self.ctx = ctx

        self.log = get_logger('Overlay.Server')
        self.supported_methods = [func for func in dir(OverlayInterface) if callable(getattr(OverlayInterface, func)) and not func.startswith("__")]

        self.cmd_sock = self.ctx.socket(zmq.ROUTER)
        self.cmd_sock.bind(CMD_URL)

        # pass both evt_sock and cmd_sock ?
        self.network = Network(Keys.vk, self.ctx)

        self.network.tasks.append(self.command_listener())

        if start:
            self.run()

    def run(self):
        raghu todo - check this start 
        Auth.setup(sk_hex=self.sk, reset_auth_folder=False)
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
                getattr(self, func)(msg[0], *data)
                # self.network.func(msg[0], *data)
            else:
                self.invalid_api_call(func)
           

    @reply
    def invalid_api_call(self, api_call):
        self.log.info('Overlay server got unsupported api call {}'.format(api_call))
        # raghu todo create std error enums to return
        return "Unsupported API"


    def is_valid_vk(self, vk):
        return vk in VKBook.get_all():

    @async_reply
    async def get_ip_from_vk(self, event_id, vk):
        # TODO perhaps return an event instead of throwing an error in production
        if not self.is_valid_vk(vk):
            # raghu todo - create event enum / class that does this
            return {
                'event': 'invalid_vk',
                'event_id': event_id,
                'vk': vk
            }

        ip = await self.network.find_ip(event_id, vk)
        if not ip:
            return {
                'event': 'not_found',
                'event_id': event_id,
                'vk': vk
            }
        return {
            'event': 'got_ip',
            'event_id': event_id,
            'ip': ip,
            'vk': vk
        }

    @async_reply
    async def get_ip_and_handshake(self, event_id, vk, domain='*', is_first_time=True):

        if not self.is_valid_vk(vk):
            # raghu todo - create event enum / class that does this
            return {
                'event': 'invalid_vk',
                'event_id': event_id,
                'vk': vk
            }

        ip, is_auth = await self.network.find_ip_and_authenticate(vk, domain, is_first_time)

        if is_auth:
            event = 'authorized_ip'
       else:
            event = 'unauthorized_ip' if ip else 'not_found'

        return {
            'event': event,
            'event_id': event_id,
            'ip': ip,
            'vk': vk
        }

    @async_reply
    async def handshake_with_ip(self, event_id, vk, ip, domain='*', is_first_time=True):
        is_auth = await self.network.authenticate(event_id, vk, ip, domain, is_first_time)
        return {
            'event': 'authorized_ip' if is_auth else 'unauthorized_ip',
            'event_id': event_id,
            'ip': ip,
            'vk': vk
        }

    @async_reply
    async def ping_ip(self, event_id, ip, is_first_time):
        status = await self.network.ping_ip(event_id, is_first_time, ip)
        return {
            'event': 'node_online' if status else 'node_offline',
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
            try:
                self.fut.set_result('done')
            except:
                self.fut.cancel()
            self.network.teardown()
            self.cmd_sock.close()
            self.log.notice('Overlay service stopped.')
        except:
            pass

