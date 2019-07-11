import zmq, zmq.asyncio, asyncio, ujson, os, uuid, json, inspect, time
from cilantro_ee.utils.keys import Keys
from cilantro_ee.protocol.overlay.interface import OverlayInterface
from cilantro_ee.constants.overlay_network import EVENT_URL, CMD_URL, CLIENT_SETUP_TIMEOUT
from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.logger.base import get_logger
from cilantro_ee.protocol.overlay.kademlia.event import Event
from cilantro_ee.protocol.overlay.kademlia.network import Network
from collections import deque
from cilantro_ee.protocol.wallet import Wallet
from cilantro_ee.protocol.overlay.kademlia.new_network import Network as NewNetwork
from cilantro_ee.constants.ports import DHT_PORT, DISCOVERY_PORT, EVENT_PORT
from cilantro_ee.constants import conf
from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.protocol.comm.services import SocketStruct, Protocols

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

# import json
# class NewOverlayServer(OverlayInterface):
#     def __init__(self, sk, ip: str, port: int, ctx: zmq.Context, bootnodes: list, initial_mn_quorum: int, initial_del_quorum: int):
#         self.wallet = Wallet(seed=bytes.fromhex(sk))
#         self.ctx = ctx
#
#         self.network = NewNetwork(wallet=self.wallet,
#                                   ctx=self.ctx,
#                                   peer_service_port=DHT_PORT,
#                                   event_publisher_port=EVENT_PORT,
#                                   initial_mn_quorum=initial_mn_quorum,
#                                   initial_del_quorum=initial_del_quorum,
#                                   bootnodes=bootnodes)
#
#         self.command_address = 'tcp://{}:{}'.format(ip, port)
#         self.command_socket = self.ctx.socket(zmq.REQ)
#         self.command_socket.bind(self.command_address)
#         self.command_listener_running = False
#
#     async def start(self):
#         await self.network.start()
#
#     async def command_listener(self):
#         self.command_listener_running = True
#         while self.command_listener_running:
#             msg = await self.command_socket.recv()
#             msg = json.loads(msg.decode())
#
#             response = self.handle_msg(msg)
#             return response
#
#     def handle_msg(self, msg):
#         command, args = msg
#         response = {}
#
#         if command == 'status':
#             if self.network.ready:
#                 response = {
#                         'event': 'service_status',
#                         'status': 'ready'
#                     }
#             else:
#                 response = {
#                     'event': 'service_status',
#                     'status': 'not_ready'
#                 }
#
#         response = json.dumps(response).encode()
#         return response


class OverlayServer():
    def __init__(self, sk, ctx, quorum):
        self.log = get_logger('Overlay.Server')
        self.sk = sk
        self.wallet = Wallet(seed=sk)
        self.loop = asyncio.get_event_loop()

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

        # pass both evt_sock and cmd_sock ?
        #self.network = Network(wallet=self.wallet, ctx=self.ctx)

        #self.network.tasks.append(self.command_listener())

        self.network = NewNetwork(wallet=self.wallet,
                                  ctx=self.ctx,
                                  ip=conf.HOST_IP,
                                  peer_service_port=DHT_PORT,
                                  event_publisher_port=EVENT_PORT,
                                  bootnodes=conf.BOOTNODES,
                                  initial_mn_quorum=PhoneBook.masternode_quorum_min,
                                  initial_del_quorum=PhoneBook.delegate_quorum_min,
                                  mn_to_find=PhoneBook.masternodes,
                                  del_to_find=PhoneBook.delegates)

    def start(self):
        self.loop.run_until_complete(asyncio.ensure_future(
            self.network.start()
        ))
        self.log.success('BOOTUP TIME')


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
        return vk in PhoneBook.all

    # seems to be a reimplementation of peer services
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

        response = await self.network.find_node(self.network_address, vk)  # 0.0.0.0 NO PORT
        ip = response.get(vk)
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

