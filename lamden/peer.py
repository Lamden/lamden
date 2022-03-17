import json
from lamden.logger.base import get_logger
import asyncio

from lamden.sockets.request import Request
from lamden.sockets.subscriber import Subscriber
from lamden.sockets.dealer import Dealer
from urllib.parse import urlparse


LATEST_BLOCK_NUM = 'latest_block_num'
GET_BLOCK = 'get_block'


class Peer:
    def __init__(self, ip, ctx, server_key, vk, services, blacklist, wallet,
                 get_network_ip, connected_callback, logger=None, testing=False, debug=False):
        self.ctx = ctx

        self.server_key = server_key
        self.vk = vk

        self.get_network_ip = get_network_ip

        self.protocol = 'tcp://'
        self.socket_ports = {
            'router': 19000,
            'publisher': 19080,
            'webserver': 18080
        }

        self.url = None
        self.set_ip(ip)

        self.services = services
        self.in_consensus = True
        self.errored = False
        self.wallet = wallet

        self.blacklist = blacklist

        self.running = False
        self.sub_running = False
        self.reconnecting = False
        self.connected_callback = connected_callback

        self.testing = testing
        self.debug = debug
        self.debug_messages = []
        self.log = logger or get_logger("PEER")

        self.dealer = None

        self.subscriber = Subscriber(
            _address=self.subscriber_address,
            _callback=self.process_subscription,
            logger=self.log
        )

        self.latest_block_info = {
            'number': 0,
            'hlc_timestamp': "0"
        }

    @property
    def ip(self):
        if not self.url:
            return None

        return self.url.hostname

    @property
    def latest_block(self):
        try:
            block_num = self.latest_block_info.get('number')
        except Exception:
            pass
        return block_num

    @property
    def latest_hlc_timestamp(self):
        try:
            hlc_timestamp = self.latest_block_info.get('hlc_timestamp')
        except Exception:
            pass
        return hlc_timestamp

    @property
    def subscriber_address(self):
        self.log.info('[PEER] PUBLISHER ADDRESS: {}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('publisher')))
        print('[{}][PEER] PUBLISHER ADDRESS: {}{}:{}'.format(self.log.name, self.protocol, self.ip, self.socket_ports.get('publisher')))
        return '{}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('publisher'))

    @property
    def dealer_address(self):
        self.log.info('[PEER] ROUTER ADDRESSS: {}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('router')))
        print('[{}][PEER] ROUTER ADDRESSS: {}{}:{}'.format(self.log.name, self.protocol, self.ip, self.socket_ports.get('router')))
        return '{}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('router'))

    def is_available(self):
        pong = self.ping()
        return pong

    def set_ip(self, address):
        self.url = urlparse(address)

        if self.url.port:
            self.socket_ports['router'] = self.url.port
            self.calc_ports()

    def calc_ports(self):
        self.socket_ports['publisher'] = 19080 + (self.socket_ports['router'] - 19000)
        self.socket_ports['webserver'] = 18080 + (self.socket_ports['router'] - 19000)

    def start(self):
        # print('Received msg from %s : %s' % (self.router_address, msg))
        if not self.dealer:
            self.dealer = Request(_id=self.wallet.verifying_key, _address=self.dealer_address, server_vk=self.server_key,
                                  wallet=self.wallet, ctx=self.ctx, logger=self.log)

        response = self.hello()

        if not response:
            return

        if not response.get('success'):
            self.log.error(f'[DEALER] Peer connection failed to {self.server_key}, ({self.dealer_address})')
            print(f'[{self.log.name}][DEALER] Peer connection failed to {self.server_key}, ({self.dealer_address})')

            if self.running:
                self.stop()
            return

        response_type = response.get('response')

        if response_type == 'pub_info':
            self.running = True
            self.latest_block_info['number'] = response.get('latest_block_num')
            self.latest_block_info['hlc_timestamp'] = response.get('latest_hlc_timestamp')

            self.log.info(f'[DEALER] Received response from authorized node with pub info')
            print(f'[{self.log.name}][DEALER] Received response from authorized node with pub info')

            if not self.sub_running:
                self.sub_running = True
                self.reconnecting = False
                self.connected_callback(vk=self.vk)
                self.loop = asyncio.new_event_loop()
                self.subscriber.start(self.loop)

    def stop(self):
        self.running = False
        if self.dealer.running:
            self.dealer.stop()
        if self.subscriber.running:
            self.subscriber.stop()

    def not_in_consensus(self):
        self.in_consensus = False

    def currently_participating(self):
        return self.in_consensus and self.running and not self.errored

    async def process_subscription(self, data):
        topic, msg = data
        services = self.services()
        processor = services.get(topic.decode("utf-8"))
        message = json.loads(msg)
        self.debug_messages.append(message)
        # print('process_subscription: {}'.format(message))
        if not message:
            self.log.error(msg)
            self.log.error(message)
        if processor is not None and message is not None:
            ## Change this to writing on a file queue
            await processor.process_message(message)

    async def reconnect_loop(self):
        self.reconnecting = True
        while self.reconnecting and not self.running:
            self.stop()
            self.start()
            await asyncio.sleep(1)
        self.reconnecting = False

    def ping(self):
        msg = json.dumps({'action': 'ping'})
        msg_json = self.send_request(msg, timeout=500, retries=5)
        if msg_json is None and not self.reconnecting:
            asyncio.ensure_future(self.reconnect_loop())
            self.log.info(f'[PEER] Could not ping {self.dealer_address}. Attempting to reconnect...')
            print(f'[{self.log.name}][PEER] Could not ping {self.dealer_address}. Attempting to reconnect...')
        return msg_json

    def hello(self):
        msg = json.dumps({'action': 'hello', 'ip': self.get_network_ip()})
        msg_json = self.send_request(msg, timeout=500, retries=5)
        return msg_json

    def get_latest_block(self):
        msg = json.dumps({'action': 'latest_block_info'})
        msg_json = self.send_request(msg)
        if (msg_json):
            if msg_json.get('response') == LATEST_BLOCK_NUM:
                self.latest_block = msg_json.get(LATEST_BLOCK_NUM)

    def get_block(self, block_num):
        msg = json.dumps({'action': 'get_block', 'block_num': block_num})
        msg_json = self.send_request(msg)
        return msg_json

    def get_node_list(self):
        msg = json.dumps({'action': 'get_node_list'})
        msg_json = self.send_request(msg)
        return msg_json

    def send_request(self, msg, timeout=200, retries=3):
        result = self.dealer.send_msg_await(msg=msg, time_out=timeout, retries=retries)
        if (result.success):
            try:
                msg_json = json.loads(result.response)
                msg_json['success'] = result.success
                return msg_json
            except:
                self.log.info(f'[PEER] failed to decode json from {self.dealer_address}: {msg_json}')
                print(f'[{self.log.name}][PEER] failed to decode json from {self.dealer_address}: {msg_json}')
                return None
