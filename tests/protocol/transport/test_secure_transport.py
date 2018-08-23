from cilantro.utils.test import MPTestCase, MPComposer, vmnet_test
from cilantro.protocol.transport import Composer
from cilantro.messages.transaction.standard import StandardTransactionBuilder
from cilantro.protocol import wallet
from cilantro.protocol.reactor.executor import *
import unittest
import time

from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_DELEGATES

W = wallet
sk1, vk1 = TESTNET_MASTERNODES[0]['sk'], TESTNET_MASTERNODES[0]['vk']
sk2, vk2 = TESTNET_DELEGATES[0]['sk'], TESTNET_DELEGATES[0]['vk']
sk3, vk3 = TESTNET_DELEGATES[1]['sk'], TESTNET_DELEGATES[1]['vk']
sk4, vk4 = TESTNET_DELEGATES[2]['sk'], TESTNET_DELEGATES[2]['vk']

# sk_sketch, vk_sketch = W.new()
sk_sketch, vk_sketch = "968017ed7931bca83dba52d80c1d759b794bad71d5679fbbafd5d4f16d4dc396", \
    "a7affe4e7a6ea87f9c680ac1fcbd2d8cda73f4419c5fd4b90f2cb579bfce2fc1"

URL = 'tcp://127.0.0.1:9988'
FILTER = 'TEST_FILTER'

FILTERS = ['FILTER_' + str(i) for i in range(100)]
URLS = ['tcp://127.0.0.1:' + str(i) for i in range(9000, 9999, 10)]

def random_msg():
    return StandardTransactionBuilder.random_tx()

def random_envelope(sk=None, tx=None):
    sk = sk or wallet.new()[0]
    tx = tx or random_msg()
    return Envelope.create_from_message(message=tx, signing_key=sk)


class TestSecureTransport(MPTestCase):

    @vmnet_test
    def test_pubsub_1_1_1_with_unauth_pub(self):
        """
        Tests pub/sub 1-1 (one sub one pub) with one message, and one
        unauthorized veriying key
        """
        def config_sub(composer: Composer):
            from unittest.mock import MagicMock

            composer.manager.router = MagicMock()
            return composer

        def assert_sub(composer: Composer):
            from cilantro.messages.reactor.reactor_command import ReactorCommand
            from cilantro.protocol.states.decorators import StateInput
            from unittest.mock import call
            # cb = ReactorCommand.create_callback(callback=StateInput.INPUT, envelope=env)
            # composer.interface.router.route_callback.assert_called_once_with(cb)

            expected_cb = call(ReactorCommand.create_callback(callback=StateInput.INPUT, envelope=env))
            unexpected_cb = call(ReactorCommand.create_callback(callback=StateInput.LOOKUP_FAILED, envelope=evil_env))

            call_args = composer.manager.router.route_callback.call_args_list

            # # DEBUG STUFF
            # from cilantro.logger.base import get_logger
            # l = get_logger("assert sub")
            # l.debug('EXPECTED')
            # l.critical(expected_cb)
            # l.debug('UNEXPECTED')
            # l.critical(unexpected_cb)
            # l.important2("got dat call args: {}".format(call_args))
            # # END DEBUG STUFF

            # composer.interface.router.route_callback.assert_has_calls([expected_cb], any_order=True)

            assert expected_cb in call_args, "Expected callback {} to be in call_args {}".format(expected_cb, call_args)
            assert unexpected_cb not in call_args, "Did not expect callback {} to be in call_args {}".format(unexpected_cb, call_args)

            # assert len(call_args) == 2, "route_callback should be called exactly twice, not {} times with {}"\
            #                             .format(len(call_args), call_args)
            # composer.interface.router.route_callback.assert_has_calls(calls, any_order=True)

        env = random_envelope()
        evil_env = random_envelope()

        sub = MPComposer(config_fn=config_sub, assert_fn=assert_sub, name='** [MN1] SUB', sk=sk1)
        pub = MPComposer(name='++ [Delegate1] PUB', sk=sk2)
        no_auth_pub = MPComposer(name='++ [Mr. Evil] PUB', sk=sk_sketch)

        sub.add_sub(vk=vk2, filter=FILTER)
        sub.add_sub(vk=vk_sketch, filter=FILTER)

        pub.add_pub(ip=pub.ip)
        no_auth_pub.add_pub(ip=no_auth_pub.ip)

        time.sleep(3.0)

        pub.send_pub_env(filter=FILTER, envelope=env)

        no_auth_pub.send_pub_env(filter=FILTER, envelope=evil_env)

        time.sleep(3.0)  # allow PUB envelopes to go through

        self.start()

    @vmnet_test
    def test_pubsub_1_1_1_with_unauth_sub(self):
        """
        Tests pub/sub 1-1 (one sub one pub) with one message, and one
        unauthorized veriying key
        """
        def config_sub(composer: Composer):
            from unittest.mock import MagicMock
            composer.manager.router = MagicMock()
            return composer

        def assert_good_sub(composer: Composer):
            from cilantro.messages.reactor.reactor_command import ReactorCommand
            from cilantro.protocol.states.decorators import StateInput
            cb = ReactorCommand.create_callback(callback=StateInput.INPUT, envelope=env)
            composer.manager.router.route_callback.assert_called_with(cb)

        def assert_bad_sub(composer: Composer):
            from cilantro.messages.reactor.reactor_command import ReactorCommand
            from cilantro.protocol.states.decorators import StateInput
            from unittest.mock import call
            cb = call(ReactorCommand.create_callback(callback=StateInput.INPUT, envelope=env))
            assert cb not in composer.manager.router.route_callback.call_args_list

        env = random_envelope()
        evil_env = random_envelope()

        sub = MPComposer(config_fn=config_sub, assert_fn=assert_good_sub, name='** [MN1] SUB', sk=sk1)
        pub = MPComposer(name='++ [Delegate1] PUB', sk=sk2)
        no_auth_sub = MPComposer(name='++ [Mr. Evil] SUB', config_fn=config_sub, assert_fn=assert_bad_sub, sk=sk_sketch)

        sub.add_sub(vk=vk2, filter=FILTER)
        no_auth_sub.add_sub(vk=vk2, filter=FILTER)

        pub.add_pub(ip=pub.ip)

        time.sleep(3.0)  # allow add pub/add sub to go through
        pub.send_pub_env(filter=FILTER, envelope=env)
        time.sleep(3.0)  # allow PUB envelopes to go through

        self.start()


if __name__ == '__main__':
    unittest.main()
