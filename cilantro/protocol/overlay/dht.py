from cilantro.protocol.overlay.discovery import Discovery
from cilantro.protocol.overlay.network import Network
from cilantro.protocol.overlay.utils import digest
from cilantro.logger import get_logger
from queue import Queue
import os, sys, uuid, time, threading, uuid, asyncio, random, warnings, logging
import zmq.auth
from multiprocessing import Process
from cilantro.db import VKBook
from cilantro.utils import ErrorWithArgs

log = get_logger(__name__)

class DHT(Discovery):
    def __init__(self, sk=None, mode='neighborhood', cmd_cli=False, block=True, loop=None, *args, **kwargs):
        self.loop = loop if loop else asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)
        self.max_wait = kwargs.get('max_wait') or self.max_wait

        self.crawler_port = os.getenv('CRAWLER_PORT', 31337)
        self.listen_for_crawlers()

        self.host_ip = os.getenv('HOST_IP', '127.0.0.1')
        self.ips = self.loop.run_until_complete(self.discover(mode))
        if len(self.ips) == 0: self.ips[self.host_ip] = int(time.time())

        self.network_port = kwargs.get('port') or os.getenv('NETWORK_PORT', 5678)
        self.start_network(sk=sk, loop=self.loop, *args, **kwargs)

        if block:
            log.debug('Server started and blocking...')
            self.loop.run_forever()

    def join_network(self):
        mn_list = VKBook.get_masternodes()
        ip_list = list(self.ips.keys())
        if self.network.ironhouse.vk not in mn_list:
            if len(ip_list) == 1:
                raise ErrorWithArgs(1, 'NotMaster', 'No nodes found, cannot bootstrap yourself because you are not a masternode')

        log.debug('Joining network: {}'.format(self.ips))
        self.loop.run_until_complete(self.network.bootstrap([(ip, self.network_port) for ip in self.ips.keys()]))

    def start_network(self, *args, **kwargs):
        try:
            self.network = Network(*args, **kwargs)
            self.join_network()
        finally:
            self.stop_discovery()
            self.network.stop()
            self.loop.stop()
