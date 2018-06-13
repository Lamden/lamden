from cilantro.protocol.overlay.discovery import Discovery
from cilantro.protocol.overlay.network import Network
from cilantro.protocol.overlay.utils import digest
from cilantro.logger import get_logger
from queue import Queue
import os, sys, uuid, time, threading, uuid, asyncio, random, warnings, logging
import zmq.auth
from multiprocessing import Process
from cilantro.db import VKBook

log = get_logger(__name__)

class DHT(Discovery):
    def __init__(self, sk=None, mode='neighborhood', cmd_cli=False, block=True, loop=None, *args, **kwargs):
        self.loop = loop if loop else asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)

        self.crawler_port = os.getenv('CRAWLER_PORT', 31337)
        self.listen_for_crawlers()

        self.host_ip = os.getenv('HOST_IP', '127.0.0.1')
        self.ips = self.loop.run_until_complete(self.discover(mode))
        if len(self.ips) == 0: self.ips[self.host_ip] = int(time.time())

        self.network_port = os.getenv('NETWORK_PORT', 5678)
        if not kwargs.get("auth_payload"): kwargs['auth_payload'] = DHT.auth_payload
        if not kwargs.get("auth_callback"): kwargs['auth_callback'] = DHT.auth_callback
        self.network = Network(sk=sk, loop=self.loop, *args, **kwargs)
        self.network.listen(self.network_port)
        self.join_network()

        if block:
            log.debug('Server started and blocking...')
            self.loop.run_forever()

    @staticmethod
    def command_line_interface(q):
        """
            Serves as the local command line interface to set or get values in
            the network.
        """
        while True:
            command = input("Enter command (e.g.: <get/set> <key> <value>):\n")
            args = list(filter(None, command.strip().split(' ')))
            if len(args) != 0: q.put(args)

    def join_network(self):
        # assert self.ips.keys() == [self.host_ip] and self.host_ip not in VKBook.get_masternodes(), 'Cannot bootstrap yourself because you are not a masternode'
        # assert len(self.ips.keys()) != 1, 'No nodes are found!'
        log.debug('Joining network: {}'.format(self.ips))
        self.loop.run_until_complete(self.network.bootstrap([(ip, self.network_port) for ip in self.ips.keys()]))

    @staticmethod
    def auth_payload():
        payload = b'4aeba121f535ac9cc2b2c6a6629988308de5fca9aadc57b2023e19e3d83f4f88'
        log.debug('Generating auth_payload of {}'.format(payload))
        # TODO in cilantro integrated tests, call VKBook.get_masternodes()
        return payload

    @staticmethod
    def auth_callback(payload):
        correct_payload = b'4aeba121f535ac9cc2b2c6a6629988308de5fca9aadc57b2023e19e3d83f4f88'
        # TODO verify that the payload is in your book
        log.debug('random_key = {}'.format(payload))
        return correct_payload == payload


if __name__ == '__main__':
    server = DHT(node_id='vk_{}'.format(os.getenv('HOST_IP', '127.0.0.1')), block=True, cmd_cli=True)
