import zmq
import asyncio
from zmq.utils import monitor
import pathlib
from zmq.auth.certs import load_certificate
from cilantro_ee.networking.parameters import Parameters, ServiceType

# Sync sockets from parameters
# If there is a difference between the sockets stored and the sockets in parameters:
# Add and connect the ones that exist
# Disconnect and close the ones that no longer are in parameters

MN = 0
DEL = 1
ALL = 2


class SecureSocketWrapper:
    def __init__(self, ctx, server_vk, socket_id, wallet, cert_dir):
        self.connected = False
        self.handshake_successful = False
        self.socket = ctx.socket(zmq.DEALER)
        self.socket.curve_secretkey = wallet.curve_sk
        self.socket.curve_publickey = wallet.curve_vk

        cert_dir = pathlib.Path.home() / cert_dir
        cert_dir.mkdir(parents=True, exist_ok=True)

        server_pub, _ = load_certificate(str(cert_dir / f'{server_vk}.key'))
        self.socket.curve_serverkey = server_pub

        self.socket.connect(str(socket_id))


class Peers:
    def __init__(self, wallet, ctx, parameters: Parameters, service_type: ServiceType, node_type: int, cert_dir='cilsocks'):
        self.wallet = wallet
        self.ctx = ctx
        self.cert_dir = cert_dir
        self.sockets = {}
        self.parameters = parameters
        self.service_type = service_type
        self.node_type = node_type

    def connect(self, socket_id, server_vk):
        s = self.sockets.get(server_vk)
        if s is not None:
            return

        socket = SecureSocketWrapper(self.ctx, server_vk, socket_id, self.wallet, self.cert_dir)

        self.sockets[server_vk] = socket

    async def send_to_peers(self, msg):
        return await asyncio.gather(*[self.send(socket.socket, msg) for socket in self.sockets.values()])

    async def send(self, socket, msg):
        s = socket.get_monitor_socket()

        event = 2
        evnt_dict = {}
        while event == 2:
            print('start')
            evnt = await s.recv_multipart()
            evnt_dict = monitor.parse_monitor_message(evnt)
            event = evnt_dict['event']
            print(evnt_dict)
        print('done')
        # If so, shoot out the message
        if event == 1 or event == 4096:
            # Event 1 = connect success / finished
            # Event 4096 = secure handshake accepted, good to send

            socket.send(msg, flags=zmq.NOBLOCK)
            # socket.close()
            return True, evnt_dict['endpoint'].decode()

        # Otherwise, close the socket. Return result and the socket for further processing / updating sockets
        # socket.close()
        return False, evnt_dict['endpoint'].decode()

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

        for vk in current - new:
            socket = self.sockets.get(vk)
            socket.close()
            del self.sockets[vk]

        for vk in new - current:
            socket = sockets.get(vk)
            self.connect(socket, vk)

