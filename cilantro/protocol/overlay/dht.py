from cilantro.protocol.overlay.discovery import Discovery
from cilantro.protocol.overlay.network import Network
from cilantro.logger import get_logger
import os, asyncio, time
from cilantro.storage.db import VKBook
from cilantro.utils import ErrorWithArgs

log = get_logger(__name__)

NETWORK_PORT_OFFSET = 1

class DHT(Discovery):
    def __init__(self, sk=None, mode='neighborhood', cmd_cli=False, block=True, loop=None, retry_discovery=3, *args, **kwargs):
        self.loop = loop if loop else asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)
        self.max_wait = kwargs.get('max_wait') or self.max_wait
        self.retry_discovery = retry_discovery

        self.crawler_port = kwargs.get('port') or os.getenv('PORT', 30001)

        self.mode = mode
        self.host_ip = os.getenv('HOST_IP', '127.0.0.1')

        self.network_port = self.crawler_port+NETWORK_PORT_OFFSET

        self.start_network(sk=sk, loop=self.loop, *args, **kwargs)

    def join_network(self):
        log.debug('Joining network begins: {}'.format(self.ips))
        start = time.time()
        self.loop.run_until_complete(self.network.bootstrap([(ip, self.network_port) for ip in self.ips.keys()]))
        end = time.time()
        log.debug('Joining network ends. ({}s)'.format(end-start))

    def discover_network(self):
        self.ips = self.loop.run_until_complete(self.discover(self.mode))
        if len(self.ips) == 0: self.ips[self.host_ip] = int(time.time())
        mn_list = VKBook.get_masternodes()
        ip_list = list(self.ips.keys())
        if self.network.ironhouse.vk not in mn_list:
            if len(ip_list) == 1: return False
        return True

    def start_network(self, *args, **kwargs):
        self.listen_for_crawlers()
        self.network = Network(network_port=self.network_port, *args, **kwargs)
        log.debug('Discovery begins...')
        start = time.time()
        while not self.discover_network():
            if self.retry_discovery == 0:
                self.cleanup()
                raise ErrorWithArgs(1, 'NotMaster', 'No nodes found, cannot bootstrap yourself because you are not a masternode')
            log.warning('No nodes found, cannot bootstrap yourself because you are not a masternode. Retrying soon...')
            self.retry_discovery -= 1
        end = time.time()
        log.debug('Discovery ends. ({}s)'.format(end-start))
        self.join_network()

    def cleanup(self):

        self.stop_discovery()
        self.network.stop()
