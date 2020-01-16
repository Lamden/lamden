import zmq, zmq.asyncio, asyncio, traceback, time
from os import getenv as env
from cilantro_ee.constants.overlay_network import *
from cilantro_ee.constants.ports import AUTH_PORT
from zmq.auth.thread import ThreadAuthenticator
from zmq.auth.asyncio import AsyncioAuthenticator
# from cilantro_ee.services.overlay.ip import *
# from cilantro_ee.core.sockets.socket_auth import SocketAuth
from cilantro_ee.core.sockets.socket import SocketUtil
from cilantro_ee.utils.keys import Keys
from cilantro_ee.core.logger import get_logger
from cilantro_ee.services.storage.vkbook import VKBook
from collections import defaultdict
from cilantro_ee.constants import conf

PhoneBook = VKBook()

class Handshake:
    def __init__(self, vk, ctx):
        self.vk = vk
        self.ctx = ctx

        self.log = get_logger('OS.Handshake')
        self.host_ip = conf.HOST_IP
        self.port = AUTH_PORT
        self.url = 'tcp://*:{}'.format(self.port)
        self.identity = '{}:{}'.format(self.vk, self.host_ip)
        
        self.server_sock = SocketUtil.create_socket(self.ctx, zmq.ROUTER)
        # not setting the identity for this socket as communication to it is always 1 on 1
        self.server_sock.curve_secretkey = Keys.private_key
        self.server_sock.curve_publickey = Keys.public_key
        self.server_sock.curve_server = True
        self.server_sock.bind(self.url)

    async def authenticate(self, event_id, vk, ip, domain, is_first_time):
        assert ip != self.host_ip, "Silly to authenticate with yourself! Check your logic!"

        start = time.time()
        authorized = False
        url = 'tcp://{}:{}'.format(ip, self.port)
        self.log.info('Sending handshake request from {} to {} (vk={})'.format(self.host_ip, ip, vk))
        client_sock = SocketUtil.create_socket(self.ctx, zmq.DEALER)  # could be simple req socket too
        client_sock.setsockopt(zmq.IDENTITY, '{}:{}'.format(self.identity, event_id).encode())
        # raghu TODO do we really need when it is bypassing the check anyway
        client_sock.curve_secretkey = Keys.private_key
        client_sock.curve_publickey = Keys.public_key
        client_sock.curve_serverkey = Keys.vk2pk(vk)
        client_sock.connect(url)
        client_sock.send_multipart([domain.encode()])

        try:
            domain = [chunk.decode() for chunk in await asyncio.wait_for(client_sock.recv_multipart(), AUTH_TIMEOUT)][0]
            self.log.info('Received a handshake reply from {} to {} (vk={})'.format(ip, self.host_ip, vk))
            authorized = self.process_handshake(ip, vk, domain)
            self.log.notice('Complete (took {}s): {} <=o= {} (vk={})'.format(time.time()-start, self.host_ip, ip, vk))
        except asyncio.TimeoutError:
            self.log.warning('Timeout (took {}s): {} <=:= {} (vk={})'.format(time.time()-start, self.host_ip, ip, vk))
        except Exception:
            self.log.error(traceback.format_exc())
        finally:
            client_sock.close()

        return authorized

    async def listen(self):
        self.log.info('Listening to other nodes on {}'.format(self.url))
        while True:
            try:
                vk_ip, domain = [chunk.decode() for chunk in await self.server_sock.recv_multipart()]
                # raghu todo also recv is_first_time flag and announce it via evt_socket
                vk, ip, event_id = vk_ip.split(':')
                self.log.info('Received a handshake request from {} (vk={}) with event_id {}'.format(ip, vk, event_id))
                authorized = self.process_handshake(ip, vk, domain)
                if authorized:
                    self.server_sock.send_multipart([vk_ip.encode(), domain.encode()])
            except Exception as e:
                self.log.error(traceback.format_exc())

    def process_handshake(self, ip, vk, domain):
        if self.validate_roles_with_domain(domain, vk):
            self.log.info('Authorized: {} <=O= {} (vk={}, domain={})'.format(self.host_ip, ip, vk, domain))
            return True
        else:
            # NOTE The sender proved that it has the VK via the router's identity frame but the sender is not found in the receiver's VKBook
            # raghu todo - could be a potential audit layer log where this unauthorized ip is blocked at some point ?
            self.log.warning('Unauthorized VK: {} <=X= {} (vk={}, domain={})'.format(self.host_ip, ip, vk, domain))
            return False

    @staticmethod
    def validate_roles_with_domain(domain, vk, roles='any'):
        if roles == 'any':
            return vk in PhoneBook.all
        else:
            if 'masternodes' in roles and vk in PhoneBook.masternodes:
                return True
            if 'witnesses' in roles and vk in PhoneBook.witnesses:
                return True
            if 'delegates' in roles and vk in PhoneBook.delegates:
                return True
        return False
