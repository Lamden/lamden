import zmq
import asyncio
from zmq.utils import monitor
import pathlib
from zmq.auth.certs import load_certificate
from cilantro_ee.networking.parameters import Parameters, ServiceType
from cilantro_ee.logger.base import get_logger
# Sync sockets from parameters
# If there is a difference between the sockets stored and the sockets in parameters:
# Add and connect the ones that exist
# Disconnect and close the ones that no longer are in parameters

MN = 0
DEL = 1
ALL = 2

## Connect and establish handshake here...

class SecureSocketWrapper:
    def __init__(self, ctx, server_vk, socket_id, wallet, cert_dir):
        self.connected = False
        self.handshake_successful = False
        self.socket = ctx.socket(zmq.DEALER)
        self.socket.curve_secretkey = wallet.curve_sk
        self.socket.curve_publickey = wallet.curve_vk

        self._id = str(socket_id)

        cert_dir = pathlib.Path.home() / cert_dir
        cert_dir.mkdir(parents=True, exist_ok=True)

        server_pub, _ = load_certificate(str(cert_dir / f'{server_vk}.key'))
        self.socket.curve_serverkey = server_pub

        self.socket.connect(str(socket_id))
        s = self.socket.get_monitor_socket()
        evnt = s.recv_multipart()
        evnt_dict = monitor.parse_monitor_message(evnt)
        print(evnt_dict)

    def close(self):
        self.socket.close()


class Peers:
    def __init__(self, wallet, ctx, parameters: Parameters, service_type: ServiceType, node_type: int, cert_dir='cilsocks'):
        self.wallet = wallet
        self.ctx = ctx
        self.cert_dir = cert_dir
        self.sockets = {}
        self.parameters = parameters
        self.service_type = service_type
        self.node_type = node_type
        self.log = get_logger('PEERS')

    def connect(self, socket_id, server_vk):
        s = self.sockets.get(server_vk)
        if s is None:
            socket = SecureSocketWrapper(self.ctx, server_vk, socket_id, self.wallet, self.cert_dir)
            self.log.info(f'Connecting to {server_vk}, {socket_id}')
            self.sockets[server_vk] = socket

    async def send_to_peers(self, msg):
        return await asyncio.gather(*[self.send(socket_wrapper, msg) for socket_wrapper in self.sockets.values()])

    async def send(self, socket_wrapper: SecureSocketWrapper, msg):
        # s = socket_wrapper.socket.get_monitor_socket()
        #
        # while not socket_wrapper.connected and not socket_wrapper.handshake_successful:
        #     evnt = await s.recv_multipart()
        #     evnt_dict = monitor.parse_monitor_message(evnt)
        #     event = evnt_dict['event']
        #     if event == 1:
        #         socket_wrapper.connected = True
        #     elif event == 4096:
        #         socket_wrapper.handshake_successful = True
        #     else:
        #         raise Exception(f'Unknown event {event} encountered on socket monitor')

        self.log.info(f'Sending message to : {socket_wrapper._id}')

        await socket_wrapper.socket.send(msg)

        self.log.info('Done')
        # socket.close()
        return True

    def sync_sockets(self):
        if self.node_type == MN:
            sockets = self.parameters.get_masternode_sockets(self.service_type)
        elif self.node_type == DEL:
            sockets = self.parameters.get_delegate_sockets(self.service_type)
        elif self.node_type == ALL:
            sockets = self.parameters.get_all_sockets(self.service_type)
        else:
            raise Exception('Invalid node type provided on initialization.')

        # Current - New = to remove
        # New - Current = to add

        new = set(sockets.keys())
        current = set(self.sockets.keys())

        if new == current:
            return

        for vk in current - new:
            socket = self.sockets.get(vk)
            socket.close()
            del self.sockets[vk]

        for vk in new - current:
            socket = sockets.get(vk)
            self.connect(socket, vk)

