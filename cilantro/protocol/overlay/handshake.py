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

class Handshake:
    log = get_logger('Handshake')
    host_ip = HOST_IP
    port = AUTH_PORT
    url = 'tcp://*:{}'.format(port)
    pepper = PEPPER.encode()
    authorized_nodes = {'*':{}}
    unknown_authorized_nodes = {}
    is_setup = False

    @classmethod
    def setup(cls, loop=None, ctx=None):
        if not cls.is_setup:
            cls.loop = loop or asyncio.get_event_loop()
            asyncio.set_event_loop(cls.loop)
            cls.ctx = ctx or zmq.asyncio.Context()
            cls.auth = AsyncioAuthenticator(context=cls.ctx, loop=cls.loop)
            cls.auth.start()
            cls.auth.configure_curve(domain="*", location=zmq.auth.CURVE_ALLOW_ANY)
            cls.sock = cls.ctx.socket(zmq.ROUTER)
            cls.sock.setsockopt(zmq.IDENTITY, cls.host_ip.encode())
            cls.sock.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
            # cls.sock.setsockopt(zmq.ROUTER_HANDOVER, 1)  # FOR DEBUG ONLY
            cls.sock.curve_secretkey = Auth.private_key
            cls.sock.curve_publickey = Auth.public_key
            cls.sock.curve_server = True
            cls.sock.bind(cls.url)
            cls.is_setup = True

    @classmethod
    async def initiate_handshake(cls, ip, vk, domain='*'):
        if ip == cls.host_ip and vk == Auth.vk:
            cls.authorized_nodes[domain][vk] = ip
            Auth.add_public_key(vk=vk, domain=domain)
            return True

        start = time.time()
        if not cls.check_previously_authorized(ip, vk, domain):
            cls.log.info('Sending handshake request from {} to {} (vk={})'.format(cls.host_ip, ip, vk))
            cls.send(ip, vk, domain, 'request')
            for i in range(AUTH_TIMEOUT):
                if cls.authorized_nodes[domain].get(vk): break
                # cls.send(ip, vk, domain, 'request')
                await asyncio.sleep(AUTH_INTERVAL)
        end = time.time()

        if cls.authorized_nodes[domain].get(vk):
            cls.log.info('Complete (took {}s): {} <=o= {} (vk={})'.format(end-start, cls.host_ip, ip, vk))
            return True
        else:
            cls.log.warning('Timeout (took {}s): {} <=:= {} (vk={})'.format(end-start, cls.host_ip, ip, vk))
            cls.log.warning(cls.authorized_nodes[domain])
            return False

    @classmethod
    async def listen(cls):
        cls.log.info('Listening to other nodes on {}'.format(cls.url))
        while True:
            try:
                raw = await cls.sock.recv_multipart()
                cls.log.important(raw)
                msg = [chunk.decode() for chunk in raw]

                ip, vk, domain, msg_type = msg
                if not cls.authorized_nodes.get(domain):
                    cls.authorized_nodes[domain] = {}
                if len(msg) == 4:
                    cls.log.info('Received a handshake {} from {} (vk={}, domain={})'.format(msg_type, ip, vk, domain))
                else:
                    cls.log.warning('Received invalid message')
                    Event.emit({'event': 'invalid_msg', 'msg': msg})
                    continue

                if msg_type == 'request':
                    cls.log.info('Sending handshake reply from {} to {} (vk={})'.format(cls.host_ip, ip, vk))
                    cls.send(ip, vk, domain, 'reply')

                if not cls.check_previously_authorized(ip, vk, domain):
                    if cls.validate_roles_with_domain(domain, vk):

                        cls.authorized_nodes[domain][vk] = ip
                        cls.authorized_nodes['*'][vk] = ip # Set all category for easier look-up
                        Auth.add_public_key(vk=vk, domain=domain)
                        # Only reply to requests

                        cls.log.info('Authorized: {} <=O= {} (vk={})'.format(cls.host_ip, ip, vk))
                        Event.emit({'event': 'authorized', 'vk': vk, 'ip': ip})
                    else:
                        cls.unknown_authorized_nodes[vk] = ip
                        Auth.remove_public_key(vk=vk, domain=domain)
                        # NOTE The sender proved that it has the VK via ZMQ Auth but the sender is not found in the receiver's VKBook
                        cls.log.important('Unknown VK: {} <=X= {} (vk={}, domain={}), saving to unknown_authorized_nodes for now'.format(cls.host_ip, ip, vk, domain))
                        Event.emit({'event': 'unknown_vk', 'vk': vk, 'ip': ip})
            except Exception as e:
                cls.log.error(traceback.format_exc())

    @classmethod
    def send(cls, ip, vk, domain, msg_type='request'):
        cls.sock.curve_serverkey = Auth.vk2pk(vk)
        if msg_type == 'request':
            cls.sock.connect('tcp://{}:{}'.format(ip, cls.port))
            time.sleep(0.5)
        cls.sock.send_multipart([ip.encode(), Auth.vk.encode(), domain.encode(), msg_type.encode()])
        time.sleep(0.5)

    @classmethod
    def check_previously_authorized(cls, ip, vk, domain):
        if not cls.authorized_nodes.get(domain):
            cls.authorized_nodes[domain] = {}
        if cls.authorized_nodes[domain].get(ip):
            cls.log.spam('Previously Authorized: {} <=O= {} (vk={}, domain={})'.format(cls.host_ip, ip, vk, domain))
            return True
        elif cls.authorized_nodes['*'].get(vk):
            if ip == cls.authorized_nodes['*'][vk]:
                cls.log.spam('Already Authorized To Domain: {} <=O= {} (vk={}, domain={})'.format(cls.host_ip, ip, vk, domain))
                cls.authorized_nodes[domain][vk] = ip
                return True
        elif cls.unknown_authorized_nodes.get(vk):
            if ip == cls.unknown_authorized_nodes[vk]:
                cls.log.spam('Found and authorized previously unknown but authorized node: {} <=O= {} (vk={}, domain={})'.format(cls.host_ip, ip, vk, domain))
                cls.authorized_nodes['*'][vk] = ip
                cls.authorized_nodes[domain][vk] = ip
            else:
                cls.log.spam('Removing stale unknown VK: {} =||= {} (vk={})'.format(cls.host_ip, ip, vk))
            del cls.unknown_authorized_nodes[vk]
        return False

    @classmethod
    def validate_roles_with_domain(cls, domain, vk):
        if domain == '*':
            return Auth.auth_validate(vk, 'any')
        elif domain == 'block-aggregator':
            return Auth.auth_validate(vk, ['masternodes', 'delegates'])
        # elif domain == 'relay-tx':
        #     return Auth.auth_validate(vk, ['masternodes', 'witnesses'])
        # NOTE etc...
