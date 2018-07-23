from cilantro import Constants
from cilantro.utils.test import MPTesterBase, MPTestCase, mp_testable, MPComposer, vmnet_test
from cilantro.protocol.transport import Router, Composer
from cilantro.protocol.reactor import ReactorInterface
from cilantro.messages import *
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.protocol.reactor.executor import *
from cilantro.db import VKBook
import asyncio
import unittest
import time


W = Constants.Protocol.Wallets
sk1, vk1 = Constants.Testnet.Masternodes[0]['sk'], Constants.Testnet.Masternodes[0]['vk']
sk2, vk2 = Constants.Testnet.Delegates[0]['sk'], Constants.Testnet.Delegates[0]['vk']
sk3, vk3 = Constants.Testnet.Delegates[1]['sk'], Constants.Testnet.Delegates[1]['vk']
sk4, vk4 = Constants.Testnet.Delegates[2]['sk'], Constants.Testnet.Delegates[2]['vk']

URL = 'tcp://127.0.0.1:9988'
FILTER = 'TEST_FILTER'

FILTERS = ['FILTER_' + str(i) for i in range(100)]
URLS = ['tcp://127.0.0.1:' + str(i) for i in range(9000, 9999, 10)]


def random_msg():
    return StandardTransactionBuilder.random_tx()

def random_envelope(sk=None, tx=None):
    sk = sk or ED25519Wallet.new()[0]
    tx = tx or random_msg()
    return Envelope.create_from_message(message=tx, signing_key=sk)


class TestTransportIntegration(MPTestCase):

    @vmnet_test
    def test_pubsub_network(self):
        def config_sub(composer: Composer):
            from unittest.mock import MagicMock

            composer.interface.router = MagicMock()
            return composer

        def assert_sub(composer: Composer):
            from cilantro.messages import ReactorCommand, Envelope
            from cilantro.protocol.statemachine.decorators import StateInput
            cb = ReactorCommand.create_callback(callback=StateInput.INPUT, envelope=env)
            composer.interface.router.route_callback.assert_called_once_with(cb)

        env = random_envelope()

        sub = MPComposer(config_fn=config_sub, assert_fn=assert_sub, name='** [MN1] SUB', sk=sk1)
        pub = MPComposer(name='++ [Delegate1] PUB', sk=sk2)
        pub_ip = pub.ip

        sub.add_sub(vk=vk2, filter=FILTER)
        pub.add_pub(ip=pub_ip)

        time.sleep(3.0)

        pub.send_pub_env(filter=FILTER, envelope=env)

        self.start()


if __name__ == '__main__':
    unittest.main()
