import json
from datetime import datetime

from lamden.logger.base import get_logger
import asyncio
from lamden.sockets.subscriber import Subscriber
from lamden.sockets.dealer import Dealer
from lamden.crypto import wallet
import codecs
from zmq.utils import z85
from nacl.bindings import crypto_sign_ed25519_pk_to_curve25519

WORK_SERVICE = 'work'


class Peer:
    def __init__(self, ip, socket_ports, ctx, key, services, blacklist, max_strikes, wallet, testing=False, debug=False):
        self.ctx = ctx
        self.ip = ip
        self.socket_ports = socket_ports
        self.server_key = key
        self.services = services
        self.in_consensus = True
        self.errored = False
        self.wallet = wallet

        self.max_strikes = max_strikes
        self.strikes = 0

        self.blacklist = blacklist

        self.log = get_logger("PEER")
        self.running = False
        self.sub_running = False

        self.testing = testing
        self.debug = debug
        self.debug_messages = []

        self.sub_running = False
        self.subscriber = Subscriber(
            _address=self.subscriber_address,
            _callback=self.process_subscription
        )

    @property
    def subscriber_address(self):
        self.log.info('PEER PUBLISHER ADDRESS: {}:{}'.format(self.ip, self.socket_ports.get('publisher')))
        return '{}:{}'.format(self.ip, self.socket_ports.get('publisher'))

    @property
    def dealer_address(self):
        self.log.info('PEER ROUTER ADDRESSS: {}:{}'.format(self.ip, self.socket_ports.get('router')))
        return '{}:{}'.format(self.ip, self.socket_ports.get('router'))

    def start(self):
        print('starting dealer connecting to: ' + self.dealer_address)
        self.loop = asyncio.new_event_loop()
        self.dealer = Dealer(_id=self.wallet.verifying_key, _address=self.dealer_address, server_vk=self.server_key,
                             wallet=self.wallet, ctx=self.ctx, _callback=self.dealer_callback)
        self.dealer.start()


    def dealer_callback(self, msg):
        print('Peer received msg from %s : %s' % (self.dealer_address, msg))

        if (msg == Dealer.con_failed):
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + f': Peer {self.server_key} connection failed to {self.dealer_address}')
            return

        try:
            msg_json = json.loads(msg)
        except:
            print(f'Peer {self.server_key} failed to decode json from {msg}')
            return

        sub_running = self.sub_running

        if (not self.sub_running and
                'response' in msg_json and
                msg_json['response'] == 'pub_info'):
            self.sub_running = True
            self.running = True
            print('Received response from authorized master with pub info')
            self.subscriber.start(self.loop)
        elif msg == Dealer.con_failed:
            self.log.error('Peer connection failed to %s (%s)' % (self.server_key, self.router_address))
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
            '''
            if self.debug:
                if topic.decode("utf-8") == WORK_SERVICE:
                    self.log.debug(json.dumps({
                        'type': 'tx_lifecycle',
                        'file': 'new_sockets',
                        'event': 'processing_from_socket',
                        'hlc_timestamp': message['hlc_timestamp'],
                        'system_time': time.time()
                    }))
            '''
            await processor.process_message(message)

    # def z85_key(key):
    #     bvk = bytes.fromhex(key)
    #     try:
    #         pk = crypto_sign_ed25519_pk_to_curve25519(bvk)
    #     # Error is thrown if the VK is not within the possibility space of the ED25519 algorithm
    #     except RuntimeError:
    #         return
    #
    #     return z85.encode(pk).decode('utf-8')
