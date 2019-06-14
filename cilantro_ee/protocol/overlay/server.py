import zmq, zmq.asyncio, asyncio, ujson, os, uuid, json, inspect, time
from cilantro_ee.utils.keys import Keys
from cilantro_ee.protocol.overlay.interface import OverlayInterface
from cilantro_ee.constants.overlay_network import EVENT_URL, CMD_URL, CLIENT_SETUP_TIMEOUT
from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.logger.base import get_logger
from cilantro_ee.protocol.overlay.kademlia.event import Event
from cilantro_ee.protocol.overlay.kademlia.network import Network
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
    def __init__(self, sk, ctx, quorum):
        self.log = get_logger('Overlay.Server')
        self.sk = sk
        Keys.setup(sk_hex=self.sk)
        self.loop = asyncio.get_event_loop()
        self.ctx = ctx
        if quorum <= 0:
            self.log.critical("quorum value should be greater than 0 for overlay server to properly synchronize!")

        self.quorum = quorum

        self.supported_methods = [func for func in dir(OverlayInterface) if callable(getattr(OverlayInterface, func)) and not func.startswith("__")]

        self.cmd_sock = self.ctx.socket(zmq.ROUTER)
        self.cmd_sock.bind(CMD_URL)

        # pass both evt_sock and cmd_sock ?
        self.network = Network(Keys.vk, self.ctx)

        self.network.tasks.append(self.command_listener())

    def start(self):
        self.network.start()
        if self.quorum == 0:
            self.network.bootup()

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
                raise Exception("Unsupported API call {}".format(func))
           

    @async_reply
    async def ready(self, *args, **kwargs):
        self.log.debugv('Overlay Client # {} ready!'.format(self.quorum))
        self.quorum = self.quorum - 1
        if self.quorum == 0:
            await self.network.bootup()
        return {
            'event': 'service_status',
            'status': 'not_ready'
        }


    @reply
    def invalid_api_call(self, api_call):
        self.log.info('Overlay server got unsupported api call {}'.format(api_call))
        # raghu todo create std error enums to return
        return "Unsupported API"

    def is_valid_vk(self, vk):
        return vk in PhoneBook.all

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
    async def get_ip_and_handshake(self, event_id, vk, is_first_time):

        if not self.is_valid_vk(vk):
            # raghu todo - create event enum / class that does this
            return {
                'event': 'invalid_vk',
                'event_id': event_id,
                'vk': vk
            }

        ip, is_auth = await self.network.find_ip_and_authenticate(event_id, vk, is_first_time)

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
    async def handshake_with_ip(self, event_id, vk, ip, is_first_time):
        is_auth = await self.network.ping_ip(event_id, vk, ip, is_first_time)
        return {
            'event': 'authorized_ip' if is_auth else 'unauthorized_ip',
            'event_id': event_id,
            'ip': ip,
            'vk': vk
        }

    @async_reply
    async def ping_ip(self, event_id, vk, ip, is_first_time):
        status = await self.network.ping_ip(event_id, vk, ip, is_first_time)
        return {
            'event': 'node_online' if status else 'node_offline',
            'event_id': event_id,
            'ip': ip
        }


    @reply
    def get_service_status(self, event_id):
        if self.network.is_connected:
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
            try:
                self.fut.set_result('done')
            except:
                self.fut.cancel()
            self.network.teardown()
            self.cmd_sock.close()
            self.log.notice('Overlay service stopped.')
        except:
            pass

