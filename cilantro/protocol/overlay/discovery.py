import zmq, zmq.asyncio, asyncio, traceback
from os import getenv as env
from cilantro.constants.overlay_network import *
from cilantro.protocol.overlay.ip import *
from cilantro.protocol.overlay.auth import Auth
from cilantro.logger import get_logger

class Discovery:
    log = get_logger('Discovery')
    host_ip = env('HOST_IP')
    port = env('DISCOVERY_PORT', 20001)
    url = 'tcp://*:{}'.format(port)
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.ROUTER)
    pepper = env('PEPPER', 'ciltantro_code').encode()
    discovered_nodes = {}
    connections = {}

    @classmethod
    async def listen(cls):
        cls.sock.setsockopt(zmq.IDENTITY, cls.host_ip.encode())
        cls.sock.bind(cls.url)
        cls.log.info('Listening to other nodes on {}'.format(cls.url))
        cls.discovered_nodes[Auth.vk] = cls.host_ip
        while True:
            try:
                msg = await cls.sock.recv_multipart()
                ip, pepper = msg[:2]
                assert pepper == cls.pepper, 'Node not using cilantro'
                if len(msg) == 2:
                    cls.reply(ip)
                elif len(msg) == 3:
                    vk = msg[-1]
                    cls.discovered_nodes[vk.decode()] = ip.decode()
            except Exception as e:
                cls.log.error(traceback.format_exc())

    @classmethod
    async def discover_nodes(cls, start_ip):
        while True:
            cls.log.info('Connecting to this ip-range: {}'.format(start_ip))
            cls.connect(get_ip_range(start_ip))
            await asyncio.sleep(DISCOVERY_TIMEOUT)
            if len(cls.discovered_nodes) >= MIN_BOOTSTRAP_NODES:
                cls.log.info('Found {} nodes to bootstrap.'.format(
                    len(cls.discovered_nodes)
                ))
                return cls.discovered_nodes
            else:
                cls.log.info('Did not find enough nodes ({}/{}).'.format(
                    len(cls.discovered_nodes),
                    MIN_BOOTSTRAP_NODES
                ))

    @classmethod
    def request(cls, ip):
        cls.sock.send_multipart([ip, cls.pepper])

    @classmethod
    def reply(cls, ip):
        cls.sock.send_multipart([ip, cls.pepper, Auth.vk.encode()])

    @classmethod
    def connect(cls, ips):
        for ip in ips:
            url = 'tcp://{}:{}'.format(ip, cls.port)
            cls.sock.connect(url)
            cls.connections[ip] = url
            cls.request(ip.encode())
