import zmq, zmq.asyncio, asyncio
from os import getenv as env
from cilantro.overlay.auth import Auth
from cilantro.storage.db import VKBook

class Discovery:
    host_ip = env('HOST_IP')
    port = env('DISCOVERY_PORT', 20001)
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.ROUTER)
    pepper = env('PEPPER', 'ciltantro_code').encode()

    @classmethod
    def validate_vk(cls):
        return vk in VKBook.get_all()

    @classmethod
    async def create_server(cls):
        assert cls.host_ip, 'Host IP not specified'
        cls.sock.setsockopt(zmq.IDENTITY, Auth.vk)
        cls.sock.bind('tcp://{}:{}'.format(cls.host_ip, cls.port))
        while True:
            try:
                vk, pepper, ip = await cls.sock.recv_multipart()


    @classmethod
    async def discovery_nodes(cls, ips):
        for ip in ips:
            cls.sock.connect('tcp://{}:{}'.format(ip, cls.port))
            cls.sock.send_multipart([cls.pepper, cls.host_ip.encode()])
