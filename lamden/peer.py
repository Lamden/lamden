import json
from lamden.logger.base import get_logger
import asyncio

from lamden.sockets.request import Request
from lamden.sockets.subscriber import Subscriber
from lamden.sockets.dealer import Dealer


LATEST_BLOCK_NUM = 'latest_block_num'
GET_BLOCK = 'get_block'

class Peer:
    def __init__(self, ip, ctx, server_key, vk, services, blacklist, max_strikes, wallet, network_services,
                 get_network_ip, logger=None, testing=False, debug=False):
        self.ctx = ctx

        self.server_key = server_key
        self.vk = vk

        self.get_network_ip = get_network_ip
        self.ip = ip
        self.socket_ports = {
            'router': 19000,
            'publisher': 19080,
            'webserver': 18080
        }
        self.check_ip_for_port()

        self.services = services
        self.in_consensus = True
        self.errored = False
        self.wallet = wallet

        self.max_strikes = max_strikes
        self.strikes = 0

        self.blacklist = blacklist

        self.network_services = network_services

        self.running = False
        self.sub_running = False
        self.catchup = False

        self.testing = testing
        self.debug = debug
        self.debug_messages = []
        self.log = logger or get_logger("PEER")

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
    def latest_block(self):
        return self.latest_block_info.get('number')

    @property
    def latest_hlc_timestamp(self):
        return self.latest_block_info.get('hlc_timestamp')

    @property
    def subscriber_address(self):
        self.log.info('[PEER] PUBLISHER ADDRESS: {}:{}'.format(self.ip, self.socket_ports.get('publisher')))
        print('[{}][PEER] PUBLISHER ADDRESS: {}:{}'.format(self.log.name, self.ip, self.socket_ports.get('publisher')))
        return '{}:{}'.format(self.ip, self.socket_ports.get('publisher'))

    @property
    def dealer_address(self):
        self.log.info('[PEER] ROUTER ADDRESSS: {}:{}'.format(self.ip, self.socket_ports.get('router')))
        print('[{}][PEER] ROUTER ADDRESSS: {}:{}'.format(self.log.name, self.ip, self.socket_ports.get('router')))
        return '{}:{}'.format(self.ip, self.socket_ports.get('router'))

    def is_available(self):
        pong = self.ping()
        return pong

    def check_ip_for_port(self):
        try:
            protocol, ip, port = self.ip.split(":")

            self.socket_ports['router'] = int(port)
            self.socket_ports['publisher'] = 19080 + (int(port) - 19000)
            self.socket_ports['webserver'] = 18080 + (int(port) - 19000)

            self.ip = '{}:{}'.format(protocol, ip)

        except ValueError:
            return

    # def start(self):
    #     # print('starting dealer connecting to: ' + self.router_address)
    #     self.loop = asyncio.new_event_loop()
    #     self.dealer = Dealer(_id=self.wallet.verifying_key, _address=self.dealer_address, server_vk=self.server_key,
    #                          wallet=self.wallet, ctx=self.ctx, _callback=self.dealer_callback, logger=self.log)
    #     self.dealer.start()

    def start(self):
        # print('Received msg from %s : %s' % (self.router_address, msg))
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

    def add_strike(self):
        self.strikes += 1
        self.log.error(f'Strike {self.strikes} for peer {self.server_key[:8]}')
        # TODO if self.strikes == self.max_strikes then blacklist this peer or something
        if self.strikes == self.max_strikes:
            self.stop()
            self.blacklist(self.server_key)

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
            await processor.process_message(message)

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
