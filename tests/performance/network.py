from cilantro.utils.test import MPTestCase, MPComposer, vmnet_test
from cilantro.protocol.transport import Composer
from cilantro.protocol.wallet import Wallet
from cilantro.messages.transaction.standard import StandardTransactionBuilder
from cilantro.protocol.reactor.executor import *
import unittest
import time

from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_DELEGATES


W = Wallet
sk1, vk1 = TESTNET_MASTERNODES[0]['sk'], TESTNET_MASTERNODES[0]['vk']
sk2, vk2 = TESTNET_DELEGATES[0]['sk'], TESTNET_DELEGATES[0]['vk']
sk3, vk3 = TESTNET_DELEGATES[1]['sk'], TESTNET_DELEGATES[1]['vk']
sk4, vk4 = TESTNET_DELEGATES[2]['sk'], TESTNET_DELEGATES[2]['vk']

URL = 'tcp://127.0.0.1:9988'
FILTER = 'TEST_FILTER'

FILTERS = ['FILTER_' + str(i) for i in range(100)]
URLS = ['tcp://127.0.0.1:' + str(i) for i in range(9000, 9999, 10)]


def random_msg():
    return StandardTransactionBuilder.random_tx()

def random_envelope(sk=None, tx=None):
    sk = sk or Wallet.new()[0]
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
            from cilantro.messages.reactor.reactor_command import ReactorCommand
            from cilantro.protocol.states.decorators import StateInput
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
