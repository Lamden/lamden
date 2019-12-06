import zmq
import zmq.asyncio
import asyncio
import json
from cilantro_ee.utils.keys import Keys
from cilantro_ee.services.overlay.interface import OverlayInterface
from cilantro_ee.constants.overlay_network import CMD_URL
from cilantro_ee.core.logger.base import get_logger
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.services.overlay.network import Network
from cilantro_ee.constants.ports import DHT_PORT, EVENT_PORT
from cilantro_ee.constants import conf
from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.core.sockets.services import _socket, SocketStruct, SocketEncoder

def no_reply(fn):
    def _no_reply(self, *args, **kwargs):
        id_frame = args[0]
        fut = asyncio.ensure_future(fn(self, *args[1:], **kwargs))
    return _no_reply


def reply(fn):
    def _reply(self, *args, **kwargs):
        id_frame = args[0]
        res = fn(self, *args[1:], **kwargs)
        self.cmd_sock.send_multipart([
            id_frame,
            json.dumps(res, cls=SocketEncoder).encode()
        ])
    return _reply


log = get_logger('Overlay.Server')


def async_reply(fn):
    def _reply(self, *args, **kwargs):
        def _done(fut):
            self.cmd_sock.send_multipart([
                id_frame,
                json.dumps(fut.result(), cls=SocketEncoder).encode()
            ])
        id_frame = args[0]
        fut = asyncio.ensure_future(fn(self, *args[1:], **kwargs))
        fut.add_done_callback(_done)

    return _reply


class OverlayServer:
    def __init__(self, sk, ctx, quorum):
        self.log = get_logger('Overlay.Server')
        self.sk = sk
        self.wallet = Wallet(seed=sk)
        self.loop = asyncio.get_event_loop()

        self.vkbook = VKBook()

        Keys.setup(sk_hex=self.sk)

        self.loop = asyncio.get_event_loop()
        self.ctx = ctx
        if quorum <= 0:
            self.log.critical("quorum value should be greater than 0 for overlay server to properly synchronize!")

        self.quorum = quorum

        self.supported_methods = [func for func in dir(OverlayInterface) if callable(getattr(OverlayInterface, func)) and not func.startswith("__")]

        self.cmd_sock = self.ctx.socket(zmq.ROUTER)
        self.cmd_sock.bind(CMD_URL)

        self.network_address = 'tcp://{}:{}'.format(conf.HOST_IP, DHT_PORT)

        self.network = Network(wallet=self.wallet,
                                  ctx=self.ctx,
                                  ip=conf.HOST_IP,
                                  peer_service_port=DHT_PORT,
                                  event_publisher_port=EVENT_PORT,
                                  bootnodes=conf.BOOTNODES,
                                  initial_mn_quorum=self.vkbook.masternode_quorum_min,
                                  initial_del_quorum=self.vkbook.delegate_quorum_min,
                                  mn_to_find=self.vkbook.masternodes,
                                  del_to_find=self.vkbook.delegates)

    def start(self):
        self.loop.run_until_complete(asyncio.ensure_future(
            asyncio.gather(
                self.network.start(),
                self.command_listener()
            )
        ))

    async def command_listener(self):
        self.log.info('Listening for overlay commands over {}'.format(CMD_URL))
        while True:
            msg = await self.cmd_sock.recv_multipart()
            self.log.success('GOT SOMETHING: {}'.format(msg))
            self.log.debug('[Overlay] Received cmd (Proc={}): {}'.format(msg[0], msg[1:]))
            data = [b.decode() for b in msg[2:]]

            # getattr(self, msg[1].decode())(msg[0], *data)
            func = msg[1].decode()
            if func in self.supported_methods:
                getattr(self, func)(msg[0], *data)
                # self.network.func(msg[0], *data)
            else:
                raise Exception("Unsupported API call {}".format(func))


    @no_reply
    async def ready(self, *args, **kwargs):
        self.log.debugv('Overlay Client # {} ready!'.format(self.quorum))
        self.quorum = self.quorum - 1
        if self.quorum == 0:
            await self.network.bootup()

    @reply
    def invalid_api_call(self, api_call):
        self.log.info('Overlay server got unsupported api call {}'.format(api_call))
        # raghu todo create std error enums to return
        return "Unsupported API"

    def is_valid_vk(self, vk):
        return vk in self.vkbook.masternodes or \
               vk in self.vkbook.delegates or \
               vk in self.vkbook.witnesses 

    # seems to be a reimplementation of peer services
    @async_reply
    async def get_ip_from_vk(self, event_id, vk):
        # TODO perhaps return an event instead of throwing an error in production
        self.log.info('Time to give them a vk :'.format(vk))
        if not self.is_valid_vk(vk):
            # raghu todo - create event enum / class that does this
            return {
                'event': 'invalid_vk',
                'event_id': event_id,
                'vk': vk
            }

        response = await self.network.find_node(self.network_address, vk)  # 0.0.0.0 NO PORT
        ip = response.get(vk) if response else None
        if not ip:
            return {
                'event': 'not_found',
                'event_id': event_id,
                'vk': vk
            }

        if SocketStruct.is_valid(ip):
            ip = SocketStruct.from_string(ip).id

        return {
            'event': 'got_ip',
            'event_id': event_id,
            'ip': ip,
            'vk': vk
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

