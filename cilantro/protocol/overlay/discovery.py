import zmq, zmq.asyncio, asyncio
from os import getenv as env

class DiscoveryMsg:
    @classmethod
    def pack(cls):
        pass

    @classmethod
    def unpack(cls):
        pass

class Discovery:
    host_ip = env('HOST_IP')
    port = env('DISCOVERY_PORT', 20001)
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.ROUTER)

    @classmethod
    async def create_server(cls):
        assert cls.host_ip, 'Host IP not specified'
        cls.sock.bind('tcp://{}:{}'.format(cls.host_ip, cls.port))
        while True:
            try:
                msg = await cls.sock.recv()
                
