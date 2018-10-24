import zmq, zmq.asyncio, asyncio, traceback, time
from os import getenv as env
from cilantro.constants.overlay_network import *
from cilantro.constants.ports import AUTH_PORT
from zmq.auth.thread import ThreadAuthenticator
from zmq.auth.asyncio import AsyncioAuthenticator
from cilantro.protocol.overlay.event import Event
from cilantro.protocol.overlay.ip import *
from cilantro.protocol.overlay.auth import Auth
from cilantro.logger import get_logger
from cilantro.storage.db import VKBook
from collections import defaultdict

class Handshake:
    log = get_logger('Handshake')
    host_ip = HOST_IP
    port = AUTH_PORT
    url = 'tcp://*:{}'.format(port)
    pepper = PEPPER.encode()
    authorized_nodes = defaultdict(dict)
    authorized_nodes['*'] = {}
    unknown_authorized_nodes = {}
    is_setup = False

    @classmethod
    def setup(cls, loop=None, ctx=None):
        if not cls.is_setup:
            cls.loop = loop or asyncio.get_event_loop()
            # asyncio.set_event_loop(cls.loop)
            cls.ctx = ctx or zmq.asyncio.Context()
            cls.identity = '{};{}'.format(cls.host_ip, Auth.vk).encode()
            cls.auth = AsyncioAuthenticator(context=cls.ctx, loop=cls.loop)
            cls.auth.configure_curve(domain="*", location=zmq.auth.CURVE_ALLOW_ANY)
            cls.auth.start()

            cls.server_sock = cls.ctx.socket(zmq.ROUTER)
            cls.server_sock.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
            cls.server_sock.curve_secretkey = Auth.private_key
            cls.server_sock.curve_publickey = Auth.public_key
            cls.server_sock.curve_server = True
            cls.server_sock.bind(cls.url)
            cls.is_setup = True

    @classmethod
    async def initiate_handshake(cls, ip, vk, domain='*'):
        if ip == cls.host_ip and vk == Auth.vk:
            cls.authorized_nodes[domain][vk] = ip
            Auth.add_public_key(vk=vk, domain=domain)
            return True
        elif cls.check_previously_authorized(ip, vk, domain):
            return True
        else:
            start = time.time()
            authorized = False
            url = 'tcp://{}:{}'.format(ip, cls.port)
            cls.log.info('Sending handshake request from {} to {} (vk={})'.format(cls.host_ip, ip, vk))

            client_sock = cls.ctx.socket(zmq.DEALER)
            client_sock.setsockopt(zmq.IDENTITY, cls.identity)
            client_sock.curve_secretkey = Auth.private_key
            client_sock.curve_publickey = Auth.public_key
            client_sock.curve_serverkey = Auth.vk2pk(vk)
            client_sock.connect(url)
            client_sock.send_multipart([domain.encode()])

            try:
                domain = [chunk.decode() for chunk in await asyncio.wait_for(client_sock.recv_multipart(), AUTH_TIMEOUT)][0]
                cls.log.info('Received a handshake reply from {} to {} (vk={})'.format(ip, cls.host_ip, vk))
                authorized = cls.process_handshake(ip, vk, domain)
                cls.log.notice('Complete (took {}s): {} <=o= {} (vk={})'.format(time.time()-start, cls.host_ip, ip, vk))
            except asyncio.TimeoutError:
                if cls.check_previously_authorized(ip, vk, domain):
                    authorized = True
                    cls.log.notice('Complete (took {}s): {} <=o= {} (vk={})'.format(time.time()-start, cls.host_ip, ip, vk))
                else:
                    cls.log.warning('Timeout (took {}s): {} <=:= {} (vk={})'.format(time.time()-start, cls.host_ip, ip, vk))
                    cls.log.warning('Authorized nodes: {}'.format(cls.authorized_nodes[domain]))
            except Exception:
                cls.log.error(traceback.format_exc())
            finally:
                client_sock.close()

            return authorized

    @classmethod
    async def listen(cls):
        cls.log.info('Listening to other nodes on {}'.format(cls.url))
        while True:
            try:
                ip_vk, domain = [chunk.decode() for chunk in await cls.server_sock.recv_multipart()]
                ip, vk = ip_vk.split(';')
                cls.log.info('Received a handshake request from {} to {} (vk={})'.format(ip, cls.host_ip, vk))
                authorized = cls.process_handshake(ip, vk, domain)
                if authorized:
                    cls.server_sock.send_multipart([ip_vk.encode(), domain.encode()])
            except Exception as e:
                cls.log.error(traceback.format_exc())

    @classmethod
    def process_handshake(cls, ip, vk, domain):
        if cls.check_previously_authorized(ip, vk, domain):
            return True
        else:
            if cls.validate_roles_with_domain(domain, vk):
                cls.authorized_nodes[domain][vk] = ip
                cls.authorized_nodes['*'][vk] = ip
                Auth.add_public_key(vk=vk, domain=domain)
                cls.log.info('Authorized: {} <=O= {} (vk={}, domain={})'.format(cls.host_ip, ip, vk, domain))
                Event.emit({'event': 'authorized', 'vk': vk, 'ip': ip, 'domain': domain})
                return True
            else:
                cls.unknown_authorized_nodes[vk] = ip
                Auth.remove_public_key(vk=vk, domain=domain)
                # NOTE The sender proved that it has the VK via the router's identity frame but the sender is not found in the receiver's VKBook
                cls.log.warning('Unknown VK: {} <=X= {} (vk={}, domain={}), saving to unknown_authorized_nodes for now'.format(cls.host_ip, ip, vk, domain))
                Event.emit({'event': 'unknown_vk', 'vk': vk, 'ip': ip, 'domain': domain})
                return False

    @classmethod
    def check_previously_authorized(cls, ip, vk, domain):
        if not cls.authorized_nodes.get(domain):
            cls.authorized_nodes[domain] = {}
        if cls.authorized_nodes[domain].get(vk):
            cls.log.info('Previously Authorized: {} <=O= {} (vk={}, domain={})'.format(cls.host_ip, ip, vk, domain))
            return True
        elif cls.authorized_nodes['*'].get(vk):
            if ip == cls.authorized_nodes['*'][vk]:
                cls.log.info('Already Authorized To Domain: {} <=O= {} (vk={}, domain={})'.format(cls.host_ip, ip, vk, domain))
                cls.authorized_nodes[domain][vk] = ip
                return True
        elif cls.unknown_authorized_nodes.get(vk):
            if ip == cls.unknown_authorized_nodes[vk]:
                cls.log.info('Found and authorized previously unknown but authorized node: {} <=O= {} (vk={}, domain={})'.format(cls.host_ip, ip, vk, domain))
                cls.authorized_nodes['*'][vk] = ip
                cls.authorized_nodes[domain][vk] = ip
            else:
                cls.log.info('Removing stale unknown VK: {} =||= {} (vk={})'.format(cls.host_ip, ip, vk))
                del cls.unknown_authorized_nodes[vk]
            return False
        return False

    @classmethod
    def validate_roles_with_domain(cls, domain, vk, roles='any'):
        if roles == 'any':
            return vk in VKBook.get_all()
        else:
            if 'masternodes' in roles and vk in VKBook.get_masternodes():
                return True
            if 'witnesses' in roles and vk in VKBook.get_witnesses():
                return True
            if 'delegates' in roles and vk in VKBook.get_delegates():
                return True
        return False
