import zmq, zmq.asyncio, asyncio, ujson, os, uuid
from cilantro.protocol.overlay.dht import DHT
from cilantro.constants.overlay_network import ALPHA, KSIZE, MAX_PEERS
from cilantro.storage.db import VKBook
from cilantro.logger.base import get_logger

log = get_logger(__name__)

class OverlayInterface:
    """
    This class provides a high level API to interface with the overlay network
    """

    ip_vk_map = {}
    url = 'ipc://overlay-ipc-sock-{}'.format(os.getenv('HOST_IP', uuid.uuid4().hex))
    loop = asyncio.get_event_loop()

    @classmethod
    def start_service(cls, sk):
        assert not hasattr(cls, '_started'), 'DHT already started.'
        cls.ctx = zmq.asyncio.Context()
        cls.event_sock = cls.ctx.socket(zmq.PUB)
        cls.event_sock.bind(cls.url)
        cls.discovery_mode = 'test' if os.getenv('TEST_NAME') else 'neighborhood'
        cls.dht = DHT(sk=sk, mode=cls.discovery_mode, loop=cls.loop,
                  alpha=ALPHA, ksize=KSIZE, event_sock=cls.event_sock,
                  max_peers=MAX_PEERS, block=False, cmd_cli=False, wipe_certs=True)
        cls._started = True

    @classmethod
    def get_node_from_vk(cls, vk: str, timeout=3):
        node = cls.ip_vk_map.get(vk)
        if node:
            return node
        else:
            assert vk in VKBook.get_all(), "Got VK {} that is not in VKBook".format(vk, VKBook.get_all())
            try:
                node = cls.loop.run_until_complete(
                    asyncio.wait_for(cls.dht.network.lookup_ip(vk), timeout))
                cls.ip_vk_map[vk] = node
                return node
            except:
                log.notice('Did not find an ip for VK {}'.format(vk))

    @classmethod
    def overlay_event_socket(cls):
        socket = cls.ctx.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        socket.connect(cls.url)
        return socket

    @classmethod
    async def event_listener(cls, event_handler):
        log.info('Listening for overlay events over {}'.format(cls.url))
        listener_sock = cls.overlay_event_socket()
        while True:
            msg = await listener_sock.recv_json()
            event_handler(msg)

    @classmethod
    def listen_for_events(cls, event_handler):
        assert hasattr(cls, '_started'), 'Have not started the service yet!'
        cls.loop.run_until_complete(cls.event_listener(event_handler))
