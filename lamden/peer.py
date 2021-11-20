import json
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
    def __init__(self, ip, ctx, key, services, blacklist, max_strikes, wallet, testing=False, debug=False):
        self.ctx = ctx
        self.ip = ip
        self.router_address = ip.replace(':180', ':190')
        self.key = key
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

        self.subRunning = False
        self.subscriber = Subscriber(ip, [''], self.process_subscription)

    def start(self):
        # print('starting dealer connecting to: ' + self.router_address)
        self.loop = asyncio.new_event_loop()
        self.dealer = Dealer(_id=self.wallet.verifying_key, _address=self.router_address, server_vk=self.key,
                             wallet=self.wallet, ctx=self.ctx, _callback=self.dealerCallback)
        self.dealer.start()

    def dealerCallback(self, identity, msg):
        print('Delegate received msg from %s : %s' % (identity, msg))
        msgJson = json.loads(msg)
        if (not self.subRunning and
                'response' in msgJson and
                msgJson['response'] == 'pub_info'):
            self.subRunning = True
            print('Received response from authorized master with pub info')
            self.subscriber.start(self.loop)

    def stop(self):
        self.running = False
        self.dealer.stop()
        self.subscriber.stop()

    def not_in_consensus(self):
        self.in_consensus = False

    def currently_participating(self):
        return self.in_consensus and self.running and not self.errored

    def add_strike(self):
        self.strikes += 1
        self.log.error(f'Strike {self.strikes} for peer {self.key[:8]}')
        # TODO if self.strikes == self.max_strikes then blacklist this peer or something
        if self.strikes == self.max_strikes:
            self.stop()
            self.blacklist(self.key)

    async def process_subscription(self, data):
        topic, msg = data
        services = self.services()
        processor = services.get(topic.decode("utf-8"))
        message = json.loads(msg)
        print('process_subscription: {}'.format(message))
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

    def z85_key(key):
        bvk = bytes.fromhex(key)
        try:
            pk = crypto_sign_ed25519_pk_to_curve25519(bvk)
        # Error is thrown if the VK is not within the possibility space of the ED25519 algorithm
        except RuntimeError:
            return

        return z85.encode(pk).decode('utf-8')