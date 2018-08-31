import zmq, zmq.asyncio, asyncio, ujson, os, uuid
from cilantro.protocol.overlay.dht import DHT
from cilantro.constants.overlay_network import ALPHA, KSIZE, MAX_PEERS
from cilantro.storage.db import VKBook
from cilantro.logger.base import get_logger

log = get_logger(__name__)
event_url = 'ipc://overlay-event-ipc-sock-{}'.format(os.getenv('HOST_IP', 'test'))
cmd_url = 'ipc://overlay-cmd-ipc-sock-{}'.format(os.getenv('HOST_IP', 'test'))

def command(fn):
    def _command(self, *args, **kwargs):
        event_id = uuid.uuid4().hex
        log.critical("bout to send event")
        self.cmd_sock.send_multipart(['_{}'.format(fn.__name__).encode(), event_id.encode()] + [arg.encode() for arg in args])
        log.critical("event sent")
        return event_id
    return _command


class OverlayServer(object):
    def __init__(self, sk, loop=None, ctx=None, block=True):
        self._started = False

        # why are we even allowed to pass in a loop/ctx? isnt this designed to run in a stand alone process?
        # thus, shouldnt it always explicitly create/manage its own event loop?  --davis
        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.ctx = ctx or zmq.asyncio.Context()

        self.evt_sock = self.ctx.socket(zmq.PUB)
        self.evt_sock.bind(event_url)
        self.cmd_sock = self.ctx.socket(zmq.ROUTER)
        self.cmd_sock.bind(cmd_url)

        self.fut = asyncio.ensure_future(self.command_listener())

        self.discovery_mode = 'test' if os.getenv('TEST_NAME') else 'neighborhood'
        self.dht = DHT(sk=sk, mode=self.discovery_mode, loop=self.loop,
                  alpha=ALPHA, ksize=KSIZE, event_sock=self.evt_sock,
                  max_peers=MAX_PEERS, block=False, cmd_cli=False, wipe_certs=True)

        self._started = True
        log.critical('overlay server about to send READY')
        self.evt_sock.send_json({
            'event': 'service_status',
            'status': 'ready'
        })
        log.critical('ready event sent from server')
        if block:
            self.loop.run_forever()

    async def command_listener(self):
        log.info('Listening for overlay commands over {}'.format(cmd_url))
        while True:
            msg = await self.cmd_sock.recv_multipart()
            log.debug('[Overlay] Received cmd (Proc={}): {}'.format(msg[0], msg[1:]))
            data = [b.decode() for b in msg[2:]]
            getattr(self, msg[1].decode())(*data)

    def _get_node_from_vk(self, event_id, vk: str, timeout=5):
        async def coro():
            node = None
            if vk in VKBook.get_all():
                try:
                    node, cached = await asyncio.wait_for(self.dht.network.lookup_ip(vk), timeout)
                except:
                    log.notice('Did not find an ip for VK {} in {}s'.format(vk, timeout))
            if node:
                self.evt_sock.send_json({
                    'event': 'got_ip',
                    'event_id': event_id,
                    'public_key': node.public_key.decode(),
                    'ip': node.ip,
                    'vk': vk
                })
            else:
                self.evt_sock.send_json({
                    'event': 'not_found',
                    'event_id': event_id
                })
        asyncio.ensure_future(coro())

    def _get_service_status(self, event_id):
        log.critical("GETTING SERVICE STATUS")  # TODO delete
        if self._started:
            log.critical("SENDING SERVICE STATUS READY")  # TODO delete
            self.evt_sock.send_json({
                'event': 'service_status',
                'status': 'ready'
            })
        else:
            log.critical("SENDING SERVICE STATUS NOT READY")  # TODO delete
            self.evt_sock.send_json({
                'event': 'service_status',
                'status': 'not_ready'
            })

    def teardown(self):
        try:
            self._started = False
            self.evt_sock.close()
            self.cmd_sock.close()
            try: self.fut.set_result('done')
            except: self.fut.cancel()
            self.dht.cleanup()
            log.info('Service stopped.')
        except:
            pass


class OverlayClient(object):
    def __init__(self, event_handler, loop, ctx, block=False):

        self.loop = loop
        self.ctx = ctx

        # DEBUG TODO DELETE
        log.important3("OverlayClient using loop {}".format(self.loop))
        # END DEBUG

        self.cmd_sock = self.ctx.socket(zmq.DEALER)
        self.cmd_sock.setsockopt(zmq.IDENTITY, str(os.getpid()).encode())
        self.cmd_sock.connect(cmd_url)
        self.evt_sock = self.ctx.socket(zmq.SUB)
        self.evt_sock.setsockopt(zmq.SUBSCRIBE, b"")
        self.evt_sock.connect(event_url)

        self.fut = asyncio.ensure_future(self.event_listener(event_handler))
        if block:
            self.loop.run_forever()

    @command
    def get_node_from_vk(self, *args, **kwargs): pass

    @command
    def get_service_status(self, *args, **kwargs): pass

    async def event_listener(self, event_handler):
        log.important('Listening for overlay events over {}'.format(event_url))  # TODO remove
        log.info('Listening for overlay events over {}'.format(event_url))
        while True:
            try:
                msg = await self.evt_sock.recv_json()
                log.important(msg)
                event_handler(msg)
            except Exception as e:
                log.warning(e)

    def teardown(self):
        self.cmd_sock.close()
        self.evt_sock.close()
        try: self.fut.set_result('done')
        except: self.fut.cancel()
