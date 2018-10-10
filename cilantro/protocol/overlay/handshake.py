import zmq, zmq.asyncio, asyncio, traceback, time
from zmq.auth.thread import ThreadAuthenticator
from zmq.auth.asyncio import AsyncioAuthenticator
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
    def setup(cls):
        if not cls.is_setup:
            cls.ctx = zmq.asyncio.Context()
            cls.server_sock = cls.ctx.socket(zmq.ROUTER)
            cls.server_sock.curve_secretkey = Auth.private_key
            cls.server_sock.curve_publickey = Auth.public_key
            cls.server_sock.curve_server = True
            cls.server_sock.setsockopt(zmq.IDENTITY, cls.host_ip.encode())
            cls.client_sock = cls.ctx.socket(zmq.ROUTER)
            cls.client_sock.curve_secretkey = Auth.private_key
            cls.client_sock.curve_publickey = Auth.public_key
            cls.client_sock.setsockopt(zmq.IDENTITY, cls.host_ip.encode())
            cls.auth = AsyncioAuthenticator(cls.ctx)
            cls.auth.configure_curve(domain="*", location=zmq.auth.CURVE_ALLOW_ANY)
            cls.auth.start()
            cls.is_setup = True

    @classmethod
    async def initiate_handshake(cls, ip, vk, domain='*'):
        if not cls.check_previously_authorized(ip, vk, domain):
            start = time.time()
            for i in range(AUTH_TIMEOUT):
                if cls.authorized_nodes[domain].get(vk): break
                cls.log.info('Sending handshake request from {} to {} (vk={})'.format(cls.host_ip, ip, vk))
                cls.request(ip, domain)
                await asyncio.sleep(AUTH_INTERVAL)
            end = time.time()

        if cls.authorized_nodes[domain].get(vk):
            cls.log.info('Complete (took {}s): {} <=o= {} (vk={})'.format(end-start, cls.host_ip, ip, vk))
            return True
        else:
            cls.log.warning('Timeout (took {}s): {} <=:= {} (vk={})'.format(end-start, cls.host_ip, ip, vk))
            return False

    @classmethod
    async def listen(cls):
        cls.server_sock.bind(cls.url)
        cls.log.info('Listening to other nodes on {}'.format(cls.url))
        while True:
            try:
                frame = await cls.sock.recv_multipart()
                ip, msg, sig = frame[0].decode(), *frame[1:3]
                signed_ip, vk, domain = msg.decode().split(';')
                assert ip == signed_ip
                is_reply = False
                if not cls.authorized_nodes.get(domain):
                    cls.authorized_nodes[domain] = {}
                if len(msg) == 3: # this is a request
                    if ip == cls.host_ip and vk == Auth.vk:
                        cls.authorized_nodes[domain][vk] = ip
                        Auth.add_public_key(vk=vk, domain=domain)
                        continue
                    else:
                        cls.log.info('Received a handshake request from {} (vk={}, domain={})'.format(ip, vk, domain))
                elif len(msg) == 4 and msg[-1] == 'rep': # this is a reply
                    cls.log.info('Received a handshake reply from {} (vk={}, domain={})'.format(ip, vk, domain))
                    is_reply = True

                if not cls.check_previously_authorized(ip, vk, domain):
                    if not Auth.verify(vk, msg, sig):
                        cls.log.important('Unauthorized: {} <=X= {} (vk={}, domain={}), cannot prove signature'.format(cls.host_ip, ip, vk, domain))
                        Event.emit({'event': 'unknown_vk', 'vk': vk, 'ip': ip})
                    elif cls.validate_roles_with_domain(domain, vk):
                        cls.authorized_nodes[domain][vk] = ip
                        cls.authorized_nodes['*'][vk] = ip # Set all category for easier look-up
                        Auth.add_public_key(vk=vk, domain=domain)
                        # Only reply to requests
                        if not is_reply: cls.reply(ip, domain)
                        cls.log.info('Authorized: {} <=O= {} (vk={})'.format(cls.host_ip, ip, vk))
                        Event.emit({'event': 'authorized', 'vk': vk, 'ip': ip})
                    else:
                        cls.unknown_authorized_nodes[vk] = ip
                        Auth.remove_public_key(vk=vk, domain=domain)
                        # NOTE The sender proved that it has the VK via ZMQ Auth but the sender is not found in the receiver's VKBook
                        cls.log.important('Unknown VK: {} <=X= {} (vk={}, domain={}), saving to unknown_authorized_nodes for now'.format(cls.host_ip, ip, vk, domain))
                        Event.emit({'event': 'unknown_vk', 'vk': vk, 'ip': ip})
                else:
                    if not is_reply: cls.reply(ip, vk, domain)
            except Exception as e:
                cls.log.warning('Received invalid message')
                Event.emit({'event': 'invalid_msg', 'frame': frame})
                cls.log.error(traceback.format_exc())

    @classmethod
    def request(cls, ip, domain):
        cls.sock.connect('tcp://{}:{}'.format(ip, cls.port))
        sig = Auth.sign(';'.join([cls.host_ip,Auth.vk,domain]).encode())
        cls.sock.send_multipart([ip.encode(), sig.message, sig.signature])

    @classmethod
    def reply(cls, ip, domain):
        cls.sock.connect('tcp://{}:{}'.format(ip, cls.port))
        sig = Auth.sign(';'.join([cls.host_ip,Auth.vk,domain]).encode())
        cls.sock.send_multipart([ip.encode(), sig.message, sig.signature, b'rep'])

    @classmethod
    def check_previously_authorized(cls, ip, vk, domain):
        if not cls.authorized_nodes.get(domain):
            cls.authorized_nodes[domain] = {}
        if cls.authorized_nodes[domain].get(ip):
            cls.log.spam('Previously Authorized: {} <=O= {} (vk={}, domain={})'.format(cls.host_ip, ip, vk, domain))
            return True
        elif cls.authorized_nodes['*'].get(ip):
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
