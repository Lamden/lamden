import json
from lamden.logger.base import get_logger
import asyncio
from lamden.sockets.subscriber import Subscriber
from lamden.sockets.dealer import Dealer

class Peer:
    def __init__(self, ip, ctx, key, services, blacklist, max_strikes, wallet, logger=None, testing=False, debug=False):
        self.ctx = ctx

        self.ip = ip
        self.socket_ports = {
            'router': 19000,
            'publisher': 19080,
            'webserver': 18080
        }
        self.check_ip_for_port()

        self.server_key = key
        self.services = services
        self.in_consensus = True
        self.errored = False
        self.wallet = wallet

        self.max_strikes = max_strikes
        self.strikes = 0

        self.blacklist = blacklist

        self.running = False
        self.sub_running = False

        self.testing = testing
        self.debug = debug
        self.debug_messages = []
        self.log = logger or get_logger("PEER")

        self.subscriber = Subscriber(
            _address=self.subscriber_address,
            _callback=self.process_subscription,
            logger=self.log
        )

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

    def check_ip_for_port(self):
        try:
            protocol, ip, port = self.ip.split(":")

            self.socket_ports['router'] = int(port)
            self.socket_ports['publisher'] = 19080 + (int(port) - 19000)
            self.socket_ports['webserver'] = 18080 + (int(port) - 19000)

            self.ip = '{}:{}'.format(protocol, ip)

        except ValueError:
            return

    def start(self):
        # print('starting dealer connecting to: ' + self.router_address)
        self.loop = asyncio.new_event_loop()
        self.dealer = Dealer(_id=self.wallet.verifying_key, _address=self.dealer_address, server_vk=self.server_key,
                             wallet=self.wallet, ctx=self.ctx, _callback=self.dealer_callback, logger=self.log)
        self.dealer.start()

    def dealer_callback(self, msg):
        # print('Received msg from %s : %s' % (self.router_address, msg))

        if (msg == Dealer.con_failed):
            self.log.info(f'[DEALER] {self.server_key} connection failed')
            print(f'[{self.log.name}][DEALER] {self.server_key} connection failed')
            return

        try:
            msg_json = json.loads(msg)
        except:
            self.log.info(f'[DEALER] failed to decode json from {msg}')
            print(f'[{self.log.name}][DEALER] failed to decode json from {msg}')
            return

        self.log.info(f'[DEALER] {msg_json}')
        print(f'[{self.log.name}][DEALER] {msg_json}')

        if (not self.sub_running and
                'response' in msg_json and
                msg_json['response'] == 'pub_info'):
            self.sub_running = True
            self.running = True

            self.log.info(f'[DEALER] Received response from authorized node with pub info')
            print(f'[{self.log.name}][DEALER] Received response from authorized node with pub info')


            self.subscriber.start(self.loop)
        elif msg == Dealer.con_failed:
            self.log.error(f'[DEALER] Peer connection failed to {self.server_key}, ({self.router_address})')
            print(f'[{self.log.name}][DEALER] Peer connection failed to {self.server_key}, ({self.router_address})')

            self.stop()

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

