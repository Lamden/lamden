import zmq, zmq.asyncio, asyncio, traceback, time
from os import getenv as env
from cilantro.constants.overlay_network import *
from cilantro.protocol.overlay.ip import *
from cilantro.protocol.overlay.auth import Auth
from cilantro.logger import get_logger

class Handshake:
    log = get_logger('Handshake')
    host_ip = env('HOST_IP')
    port = env('AUTH_PORT', 20002)
    url = 'tcp://*:{}'.format(port)
    ctx = zmq.asyncio.Context()
    server_sock = ctx.socket(zmq.ROUTER)
    client_sock = ctx.socket(zmq.ROUTER)
    pepper = env('PEPPER', 'ciltantro_code').encode()
    authorized_nodes = {'all':{}}

    @classmethod
    async def initiate_handshake(cls, ip, vk, domain='all'):
        cls.log.info('Sending handshake request from {} to {} (vk={})'.format(cls.host_ip, ip, vk))
        if not cls.authorized_nodes.get(domain):
            cls.authorized_nodes[domain] = {}
        if cls.authorized_nodes['all'].get(ip):
            if vk == cls.authorized_nodes['all'][ip]:
                cls.log.info('Authorized To Domain: {} <=O= {} (vk={}, domain={})'.format(cls.host_ip, ip, vk, domain))
                cls.authorized_nodes[domain][ip] = vk
        if cls.authorized_nodes[domain].get(ip):
            cls.log.info('Previously Authorized: {} <=O= {} (vk={}, domain={})'.format(cls.host_ip, ip, vk, domain))
            return True
        public_key = Auth.vk2pk(vk)
        cls.client_sock.curve_secretkey = Auth.private_key
        cls.client_sock.curve_publickey = Auth.public_key
        cls.client_sock.setsockopt(zmq.IDENTITY, cls.host_ip.encode())
        cls.client_sock.curve_serverkey = public_key
        cls.client_sock.connect('tcp://{}:{}'.format(ip, cls.port))

        start = time.time()
        for i in range(AUTH_TIMEOUT):
            if cls.authorized_nodes[domain].get(ip): break
            cls.request(ip, domain)
            await asyncio.sleep(AUTH_INTERVAL)
        end = time.time()
        if not cls.authorized_nodes[domain].get(ip):
            cls.log.warning('Timeout (took {}s): {} <=:= {} (vk={})'.format(end-start, cls.host_ip, ip, vk))
            cls.log.warning(cls.authorized_nodes[domain])
            return False
        cls.log.info('Complete (took {}s):'.format(end-start))
        cls.log.info(cls.authorized_nodes[domain])
        return True

    @classmethod
    async def listen(cls):
        cls.server_sock.curve_secretkey = Auth.private_key
        cls.server_sock.curve_publickey = Auth.public_key
        cls.server_sock.curve_server = True
        cls.server_sock.setsockopt(zmq.IDENTITY, cls.host_ip.encode())
        cls.server_sock.bind(cls.url)
        cls.log.info('Listening to other nodes on {}'.format(cls.url))
        while True:
            try:
                msg = [chunk.decode() for chunk \
                    in await cls.server_sock.recv_multipart()]
                ip, vk, domain = msg[:3]
                if not cls.authorized_nodes.get(domain):
                    cls.authorized_nodes[domain] = {}
                if len(msg) == 3: # this is a request
                    if ip == cls.host_ip and vk == Auth.vk:
                        cls.authorized_nodes[domain][ip] = vk
                elif len(msg) == 4: # this is a reply
                    assert msg[-1] == 'rep', 'This is not a reply'

                if cls.authorized_nodes[domain].get(ip):
                    cls.log.spam('Already Authorized: {} <=O= {} (vk={}, domain={})'.format(cls.host_ip, ip, vk, domain))
                elif cls.validate_roles_with_domain(domain, vk):
                    cls.authorized_nodes[domain][ip] = vk
                    cls.reply(ip, domain)
                    cls.log.info('Authorized: {} <=O= {} (vk={})'.format(cls.host_ip, ip, vk))
                else:
                    cls.log.warning('Unauthorized: {} <=X= {} (vk={}, domain={})'.format(cls.host_ip, ip, vk, domain))
            except Exception as e:
                cls.log.error(traceback.format_exc())

    @classmethod
    def request(cls, ip, domain):
        cls.client_sock.send_multipart([ip.encode(), Auth.vk.encode(), domain.encode()])

    @classmethod
    def reply(cls, ip, domain):
        cls.client_sock.send_multipart([ip.encode(), Auth.vk.encode(), domain.encode(), b'rep'])

    @classmethod
    def validate_roles_with_domain(cls, domain, vk):
        if domain == 'all':
            return Auth.auth_validate(vk, 'any')
        elif domain == 'block-aggregator':
            return Auth.auth_validate(vk, ['masternodes', 'delegates'])
        # elif domain == 'relay-tx':
        #     return Auth.auth_validate(vk, ['masternodes', 'witnesses'])
        # NOTE etc...
