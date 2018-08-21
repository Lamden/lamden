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

    event_url = 'ipc://overlay-event-ipc-sock-{}'.format(os.getenv('HOST_IP', ''))
    cmd_url = 'ipc://overlay-cmd-ipc-sock-{}'.format(os.getenv('HOST_IP', ''))
    loop = asyncio.get_event_loop()
    ctx = zmq.asyncio.Context()

    @classmethod
    def _start_service(cls, sk):
        assert not hasattr(cls, '_started'), 'Service already started.'
        cls.event_sock = cls.ctx.socket(zmq.PUB)
        cls.event_sock.bind(cls.event_url)
        cls.discovery_mode = 'test' if os.getenv('TEST_NAME') else 'neighborhood'
        cls.dht = DHT(sk=sk, mode=cls.discovery_mode, loop=cls.loop,
                  alpha=ALPHA, ksize=KSIZE, event_sock=cls.event_sock,
                  max_peers=MAX_PEERS, block=False, cmd_cli=False, wipe_certs=True)
        cls._started = True
        cls.loop.run_until_complete(cls._listen_for_cmds())

    @classmethod
    def _stop_service(cls):
        assert hasattr(cls, '_started'), 'Service not yet started'
        cls.event_sock.close()
        cls.cmd_sock.close()
        cls.dht.cleanup()

    @classmethod
    async def _listen_for_cmds(cls):
        log.info('Listening for overlay events over {}'.format(cls.event_url))
        cls.cmd_sock = cls.ctx.socket(zmq.ROUTER)
        cls.cmd_sock.bind(cls.cmd_url)
        while True:
            msg = await cls.cmd_sock.recv_multipart()
            log.debug('[Overlay] Received cmd (Proc={}): {}'.format(msg[0], msg[1:]))
            getattr(cls, msg[1].decode())(*msg[2:])

    @classmethod
    def _overlay_command_socket(cls):
        cls.cmd_sock = cls.ctx.socket(zmq.DEALER)
        cls.cmd_sock.setsockopt(zmq.IDENTITY, str(os.getpid()).encode())
        cls.cmd_sock.connect(cls.cmd_url)

    @classmethod
    def get_node_from_vk(cls, vk, timeout=3):
        if not hasattr(cls, 'cmd_sock'): cls._overlay_command_socket()
        cls.cmd_sock.send_multipart([b'_get_node_from_vk', vk.encode()])

    @classmethod
    def _get_node_from_vk(cls, vk: str, timeout=3):
        vk = vk.decode()
        async def coro():
            node = None
            if vk in VKBook.get_all():
                try:
                    node, cached = await asyncio.wait_for(cls.dht.network.lookup_ip(vk), timeout)
                    cls.event_sock
                except:
                    log.notice('Did not find an ip for VK {}'.format(vk))
            if node:
                cls.event_sock.send_json({
                    'status': 'success',
                    'public_key': node.public_key.decode(),
                    'ip': node.ip
                })
            else:
                cls.event_sock.send_json({
                    'status': 'not_found'
                })
        asyncio.ensure_future(coro())

    @classmethod
    def overlay_event_socket(cls):
        socket = cls.ctx.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        socket.connect(cls.event_url)
        return socket

    @classmethod
    async def event_listener(cls, event_handler):
        log.info('Listening for overlay events over {}'.format(cls.event_url))
        listener_sock = cls.overlay_event_socket()
        while True:
            msg = await listener_sock.recv_json()
            event_handler(msg)

    @classmethod
    def listen_for_events(cls, event_handler):
        cls.loop.run_until_complete(cls.event_listener(event_handler))
