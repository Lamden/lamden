import json
from lamden.logger.base import get_logger
import asyncio

from lamden.sockets.request import Request
from lamden.sockets.subscriber import Subscriber

from urllib.parse import urlparse

LATEST_BLOCK_NUM = 'latest_block_num'
GET_BLOCK = 'get_block'

class Peer:
    def __init__(self, ip, server_key, services, wallet,
                 get_network_ip, connected_callback, logger=None, driver=None, storage=None):

        self.driver = driver
        self.storage = storage

        self.server_key = server_key

        self.get_network_ip = get_network_ip

        self.protocol = 'tcp://'
        self.socket_ports = dict({
            'router': 19000,
            'publisher': 19080,
            'webserver': 18080
        })

        self.url = None
        self.set_ip(ip)

        self.services = services
        self.in_consensus = True
        self.errored = False
        self.wallet = wallet

        self.running = False
        self.sub_running = False
        self.reconnecting = False
        self.connected_callback = connected_callback

        self.log = logger or get_logger("PEER")

        self.request = None
        self.subscriber = None

        self.latest_block_info = dict({
            'number': 0,
            'hlc_timestamp': "0"
        })

        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    @property
    def vk(self):
        return self.wallet.verifying_key

    @property
    def ip(self):
        if not self.url:
            return None
        return self.url.hostname

    @property
    def latest_block_number(self):
        return self.latest_block_info.get('number')

    @property
    def latest_block_hlc_timestamp(self):
        return self.latest_block_info.get('hlc_timestamp')

    @property
    def subscriber_address(self):
        self.log.info('[PEER] PUBLISHER ADDRESS: {}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('publisher')))
        print('[{}][PEER] PUBLISHER ADDRESS: {}{}:{}'.format(self.log.name, self.protocol, self.ip, self.socket_ports.get('publisher')))
        return '{}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('publisher'))

    @property
    def request_address(self):
        self.log.info('[PEER] ROUTER ADDRESSS: {}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('router')))
        print('[{}][PEER] ROUTER ADDRESSS: {}{}:{}'.format(self.log.name, self.protocol, self.ip, self.socket_ports.get('router')))
        return '{}{}:{}'.format(self.protocol, self.ip, self.socket_ports.get('router'))

    @property
    def is_running(self):
        if not self.subscriber or not self.request:
            return False

        return self.request.is_running and self.subscriber.is_running

    def is_available(self):
        pong = self.ping()
        return pong

    def set_ip(self, address):
        self.url = urlparse(address)

        if not self.url.hostname:
            self.set_ip(address=f'{self.protocol}{address}')
        else:
            if self.url.port:
                self.socket_ports['router'] = self.url.port
                self.calc_ports()

    def set_driver(self, driver):
        self.driver = driver

    def set_storage(self, storage):
        self.storage = storage

    def set_latest_block_number(self, number):
        self.latest_block_info['number'] = number

    def set_latest_block_hlc_timestamp(self, hlc_timestamp):
        self.latest_block_info['hlc_timestamp'] = hlc_timestamp

    def calc_ports(self):
        self.socket_ports['publisher'] = 19080 + (self.socket_ports['router'] - 19000)
        self.socket_ports['webserver'] = 18080 + (self.socket_ports['router'] - 19000)


    def start(self):
        if self.running:
            self.log.error(f'[PEER] Already running.')
            print(f'[{self.log.name}][PEER] Already running.')
            return

        if not self.request:
            self.setup_request()

        response = self.hello()

        if not response:
            self.reconnect()
            return

        if not response.get('success'):
            self.log.error(f'[DEALER] Peer connection failed to {self.server_key}, ({self.request_address})')
            print(f'[{self.log.name}][DEALER] Peer connection failed to {self.server_key}, ({self.request_address})')

            self.reconnect()
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
                self.setup_subscriber()

    def setup_subscriber(self):
        self.subscriber = Subscriber(
            address=self.subscriber_address,
            callback=self.process_subscription,
            logger=self.log
        )

    def setup_request(self):
        self.request = Request(
            server_vk=self.server_key,
            wallet=self.wallet,
            logger=self.log
        )

    def stop(self):
        self.running = False
        if self.request.connected:
            self.request.stop()
        if self.subscriber.running:
            self.subscriber.stop()

    def not_in_consensus(self):
        self.in_consensus = False

    def currently_participating(self):
        return self.in_consensus and self.running and not self.errored

    async def process_subscription(self, data):
        try:
            topic, msg = data
        except ValueError as err:
            print(data)
            self.log.info(data)
            print(f'[{self.log.name}][PEER] ERROR in message: {err}')
            self.log.error(f'[PEER] ERROR in message: {err}')
            return

        services = self.services()
        processor = services.get(topic.decode("utf-8"))
        message = json.loads(msg)

        if not message:
            self.log.error(msg)
            self.log.error(message)

        if processor is not None and message is not None:
            await processor.process_message(message)

    def reconnect(self):
        asyncio.ensure_future(self.reconnect_loop())

    async def reconnect_loop(self):
        self.reconnecting = True

        while not self.is_running:
            res = self.ping()

            if res is None:
                self.log.info(f'[PEER] Could not ping {self.request_address}. Attempting to reconnect...')
                print(f'[{self.log.name}][PEER] Could not ping {self.request_address}. Attempting to reconnect...')
                await asyncio.sleep(1)

        self.log.info(f'[PEER] Reconnected to {self.request_address}!')
        print(f'[{self.log.name}][PEER] Reconnected to {self.request_address}!')

        self.reconnecting = False

    def ping(self):
        msg = json.dumps({'action': 'ping'})
        msg_json = self.send_request(msg, timeout=500, retries=5)
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
        result = self.request.send_msg_await(msg=msg, time_out=timeout, retries=retries)
        if (result.success):
            try:
                msg_json = json.loads(result.response)
                msg_json['success'] = result.success
                return msg_json
            except:
                self.log.info(f'[PEER] failed to decode json from {self.request_address}: {msg_json}')
                print(f'[{self.log.name}][PEER] failed to decode json from {self.request_address}: {msg_json}')
                return None
