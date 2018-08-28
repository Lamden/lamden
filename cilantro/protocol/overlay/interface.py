import zmq, zmq.asyncio, asyncio, ujson, os, uuid
from cilantro.protocol.overlay.dht import DHT
from cilantro.constants.overlay_network import ALPHA, KSIZE, MAX_PEERS
from cilantro.storage.db import VKBook
from cilantro.logger.base import get_logger

log = get_logger(__name__)

# ip_vk_map = {
#     '82540bb5a9c84162214c5540d6e43be49bbfe19cf49685660cab608998a65144': '172.29.5.0',  # Masternode 1
#     '0e669c219a29f54c8ba4293a5a3df4371f5694b761a0a50a26bf5b50d5a76974': '172.29.5.1',  # Witness 1
#     '50869c7ee2536d65c0e4ef058b50682cac4ba8a5aff36718beac517805e9c2c0': '172.29.5.2',  # Witness 2
#     '3dd5291906dca320ab4032683d97f5aa285b6491e59bba25c958fc4b0de2efc8': '172.29.5.3',  # Delegate 1 (aka delegate_3)
#     'ab59a17868980051cc846804e49c154829511380c119926549595bf4b48e2f85': '172.29.5.4',  # Delegate 2 (aka delegate_4)
#     '0c998fa1b2675d76372897a7d9b18d4c1fbe285dc0cc795a50e4aad613709baf': '172.29.5.5',  # Delegate 3 (aka delegate_5)
# }
#
# # TODO delete this
# nodemap = {'masternode': '172.29.5.0', 'witness_1': '172.29.5.1', 'witness_2': '172.29.5.2',
#  'delegate_3': '172.29.5.3', 'delegate_4': '172.29.5.4', 'delegate_5': '172.29.5.5',
#  'mgmt': '172.29.5.6'}

def command(fn):
    def _command(cls, *args, **kwargs):
        assert hasattr(cls, 'listener_sock'), 'You have to add an event listener first'
        if not hasattr(cls, 'cmd_send_sock'): cls._overlay_command_socket()
        event_id = uuid.uuid4().hex
        cls.cmd_send_sock.send_multipart(['_{}'.format(fn.__name__).encode(), event_id.encode()] + [arg.encode() for arg in args])
        return event_id
    return _command

class OverlayInterface(object):
    """
    This class provides a high level API to interface with the overlay network
    """

    event_url = 'ipc://overlay-event-ipc-sock-{}'.format(os.getenv('HOST_IP', 'test'))
    cmd_url = 'ipc://overlay-cmd-ipc-sock-{}'.format(os.getenv('HOST_IP', 'test'))
    loop = asyncio.new_event_loop()
    _started = False

    @classmethod
    def _start_service(cls, sk):
        ctx = zmq.asyncio.Context()
        cls.event_sock = ctx.socket(zmq.PUB)
        cls.event_sock.bind(cls.event_url)
        cls.discovery_mode = 'test' if os.getenv('TEST_NAME') else 'neighborhood'
        cls.dht = DHT(sk=sk, mode=cls.discovery_mode, loop=cls.loop,
                  alpha=ALPHA, ksize=KSIZE, event_sock=cls.event_sock,
                  max_peers=MAX_PEERS, block=False, cmd_cli=False, wipe_certs=True)
        cls._started = True
        cls.listener_fut = asyncio.ensure_future(cls._listen_for_cmds())
        cls.event_sock.send_json({ 'event': 'service_started' })
        cls.loop.run_forever()

    @classmethod
    def _stop_service(cls):
        try:
            cls._started = False
            cls.event_sock.close()
            cls.cmd_sock.close()
            try: cls.listener_fut.set_result('done')
            except: cls.listener_fut.cancel()
            cls.dht.cleanup()
            log.info('Service stopped.')
        except:
            pass

    @classmethod
    async def _listen_for_cmds(cls):
        log.info('Listening for overlay commands over {}'.format(cls.cmd_url))
        ctx = zmq.asyncio.Context()
        cls.cmd_sock = ctx.socket(zmq.ROUTER)
        cls.cmd_sock.bind(cls.cmd_url)
        while True:
            msg = await cls.cmd_sock.recv_multipart()
            log.debug('[Overlay] Received cmd (Proc={}): {}'.format(msg[0], msg[1:]))
            data = [b.decode() for b in msg[2:]]
            getattr(cls, msg[1].decode())(*data)

    @classmethod
    def _overlay_command_socket(cls):
        ctx = zmq.asyncio.Context()
        cls.cmd_send_sock = ctx.socket(zmq.DEALER)
        cls.cmd_send_sock.setsockopt(zmq.IDENTITY, str(os.getpid()).encode())
        cls.cmd_send_sock.connect(cls.cmd_url)

    @classmethod
    @command
    def get_node_from_vk(cls, *args, **kwargs): pass

    @classmethod
    def _get_node_from_vk(cls, event_id, vk: str, timeout=3):
        async def coro():
            node = None
            if vk in VKBook.get_all():
                try:
                    node, cached = await asyncio.wait_for(cls.dht.network.lookup_ip(vk), timeout)
                except:
                    log.notice('Did not find an ip for VK {}'.format(vk))
            if node:
                cls.event_sock.send_json({
                    'event': 'got_ip',
                    'event_id': event_id,
                    'public_key': node.public_key.decode(),
                    'ip': node.ip,
                    'vk': vk
                })
            else:
                cls.event_sock.send_json({
                    'event': 'not_found',
                    'event_id': event_id
                })
        asyncio.ensure_future(coro())

    @classmethod
    @command
    def get_service_status(cls, *args, **kwargs): pass

    @classmethod
    def _get_service_status(cls, event_id, vk: str, timeout=3):
        if cls._started:
            cls.event_sock.send_json({
                'event': 'service_status',
                'status': 'ready'
            })
        else:
            cls.event_sock.send_json({
                'event': 'service_status',
                'status': 'not_ready'
            })

    @classmethod
    def overlay_event_socket(cls):
        ctx = zmq.asyncio.Context()
        socket = ctx.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        socket.connect(cls.event_url)
        return socket

    @classmethod
    async def event_listener(cls, event_handler):
        log.info('Listening for overlay events over {}'.format(cls.event_url))
        cls.listener_sock = cls.overlay_event_socket()
        while True:
            try:
                msg = await cls.listener_sock.recv_json()
                event_handler(msg)
            except Exception as e:
                log.warning(e)

    @classmethod
    def stop_listening(cls):
        cls.cmd_send_sock.close()
        cls.listener_sock.close()

    @classmethod
    def listen_for_events(cls, event_handler):
cls.loop.run_until_complete(cls.event_listener(event_handler))
