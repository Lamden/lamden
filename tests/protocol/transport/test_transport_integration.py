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


class TestTransportIntegration(MPTestCase):

    @vmnet_test
    def test_pubsub_1_1_1(self):
        """
        Tests pub/sub 1-1 (one sub one pub) with one message
        """
        def assert_sub(composer: Composer):
            from cilantro.protocol.states.decorators import StateInput
            composer.manager.router.route_callback.assert_called_with(callback=StateInput.INPUT, envelope=env, message=env.message)

        env = random_envelope()

        sub = MPComposer(assert_fn=assert_sub, name='[MN1] SUB', sk=sk1)
        pub = MPComposer(name='[Delegate1] PUB', sk=sk2)
        pub_ip = pub.ip

        # Take a nap while we wait for overlay to hookup
        time.sleep(5)

        sub.add_sub(vk=vk2, filter=FILTER)
        pub.add_pub(ip=pub_ip)

        time.sleep(15.0)

        pub.send_pub_env(filter=FILTER, envelope=env)

        self.start()

    @vmnet_test
    def test_pubsub_n_1_n(self):
        """
        Tests pub/sub with 2 pubs, 1 sub, and multiple messages and the same filter
        """
        def config_sub(composer: Composer):
            from unittest.mock import MagicMock
            composer.manager.router = MagicMock()
            return composer

        def assert_sub(composer: Composer):
            from cilantro.messages.reactor.reactor_command import ReactorCommand
            from cilantro.protocol.states.decorators import StateInput
            from unittest.mock import call

            expected_calls = []
            for env in envs:
                callback = ReactorCommand.create_callback(callback=StateInput.INPUT, envelope=env)
                expected_calls.append(call(callback))

            call_args = composer.manager.router.route_callback.call_args_list
            composer.manager.router.route_callback.assert_has_calls(expected_calls, any_order=True)

        envs = [random_envelope() for _ in range(4)]

        sub = MPComposer(config_fn=config_sub, assert_fn=assert_sub, name='[MN1] SUB', sk=sk1)
        pub1 = MPComposer(name='[Delegate1] PUB1', sk=sk2)
        pub2 = MPComposer(name='[Delegate2] PUB2', sk=sk3)

        sub.add_sub(vk=vk2, filter=FILTER)
        sub.add_sub(vk=vk3, filter=FILTER)

        pub1.add_pub(ip=pub1.ip)
        pub2.add_pub(ip=pub2.ip)

        time.sleep(5.0)

        pub1.send_pub_env(filter=FILTER, envelope=envs[0])
        pub1.send_pub_env(filter=FILTER, envelope=envs[1])

        pub2.send_pub_env(filter=FILTER, envelope=envs[2])
        pub2.send_pub_env(filter=FILTER, envelope=envs[3])

        self.start()

    # TODO same test as above, but with multiple filters

    @vmnet_test
    def test_pubsub_n_1_n_removesub(self):
        """
        Tests pub/sub n-1, with a sub removing a publisher after its first message
        """
        def configure(composer: Composer):
            from unittest.mock import MagicMock
            composer.manager.router.route_callback = MagicMock()
            return composer

        def assert_sub(composer: Composer):
            from cilantro.messages.reactor.reactor_command import ReactorCommand
            from cilantro.protocol.states.decorators import StateInput
            from unittest.mock import call

            callback1 = ReactorCommand.create_callback(callback=StateInput.INPUT, envelope=env1)
            callback2 = ReactorCommand.create_callback(callback=StateInput.INPUT, envelope=env2)
            calls = [call(callback1), call(callback2)]

            call_args = composer.manager.router.route_callback.call_args_list
            composer.manager.router.route_callback.assert_has_calls(calls, any_order=True)

        env1 = random_envelope()
        env2 = random_envelope()
        env3 = random_envelope()

        sub = MPComposer(config_fn=configure, assert_fn=assert_sub, name='SUB [MN1]', sk=sk1)
        pub1 = MPComposer(name='PUB 1 [Delegate1]', sk=sk2)
        pub2 = MPComposer(name='PUB 2 [Delegate2]', sk=sk3)

        sub.add_sub(vk=vk2, filter=FILTER)  # sub to pub1
        sub.add_sub(vk=vk3, filter=FILTER)  # sub to pub2

        pub1.add_pub(ip=pub1.ip)  # Pub on its own URL
        pub2.add_pub(ip=pub2.ip)  # Pub on its own URL

        time.sleep(5.0)

        pub1.send_pub_env(filter=FILTER, envelope=env1)
        pub2.send_pub_env(filter=FILTER, envelope=env2)

        time.sleep(1.0)  # allow messages to go through
        sub.remove_sub(vk=vk3)  # unsub to pub2
        time.sleep(1.0)  # allow remove_sub_url command to go through

        pub2.send_pub_env(filter=FILTER, envelope=env3)  # this should not be recv by sub, as he removed this guy's url

        time.sleep(5.0)  # allow messages to go through before we start checking assertions

        self.start()

    @vmnet_test
    def test_pubsub_1_1_2_mult_filters(self):
        """
        Tests pub/sub 1-1 (one sub one pub) with 2 message each on a different filter
        """
        def configure(composer: Composer):
            from unittest.mock import MagicMock
            composer.manager.router = MagicMock()
            return composer

        def run_assertions(composer: Composer):
            from cilantro.messages.reactor.reactor_command import ReactorCommand
            from cilantro.protocol.states.decorators import StateInput
            from unittest.mock import call

            cb1 = ReactorCommand.create_callback(callback=StateInput.INPUT, envelope=env1)
            cb2 = ReactorCommand.create_callback(callback=StateInput.INPUT, envelope=env2)
            composer.manager.router.route_callback.assert_has_calls([call(cb1), call(cb2)], any_order=True)

        env1 = random_envelope()
        env2 = random_envelope()
        filter1 = FILTERS[0]
        filter2 = FILTERS[1]

        sub = MPComposer(config_fn=configure, assert_fn=run_assertions, name='SUB', sk=sk1)
        pub = MPComposer(name='PUB', sk=sk2)

        sub.add_sub(vk=vk2, filter=filter2)
        sub.add_sub(vk=vk2, filter=filter1)
        pub.add_pub(ip=pub.ip)

        time.sleep(5.0)  # allow time for VK lookups before we start sending things

        # Send 2 envelopes on 2 different filters
        pub.send_pub_env(filter=filter1, envelope=env1)
        pub.send_pub_env(filter=filter2, envelope=env2)

        self.start()

    @vmnet_test
    def test_req_reply_1_1_1(self):
        """
        Tests request/reply 1_1_1
        """
        def config_router(composer: Composer):
            from unittest.mock import MagicMock
            def reply(*args, **kwargs):  # do i need the *args **kwargs ??
                composer.send_reply(message=reply_msg, request_envelope=request_env)

            composer.manager.router = MagicMock()
            composer.manager.router.route_callback.side_effect = reply
            return composer

        def config_dealer(composer: Composer):
            from unittest.mock import MagicMock
            composer.manager.router = MagicMock()
            return composer

        def assert_dealer(composer: Composer):
            from cilantro.messages.reactor.reactor_command import ReactorCommand

            args = composer.manager.router.route_callback.call_args_list
            # assert len(args) == 1, "dealer's route_callback should of only been called once (with the reply env)"

            reply_callback_found = False
            for call in args:
                callback_cmd = call[0][0]
                assert isinstance(callback_cmd, ReactorCommand), "arg of route_callback should be a ReactorCommand"
                if callback_cmd.envelope and callback_cmd.envelope.message == reply_msg:
                    reply_callback_found = True
                    break
                    # assert callback_cmd.envelope.message == reply_msg, "Callback's envelope's message should be the reply_msg"
            assert reply_callback_found, "Reply callback {} not found in call args {}".format(reply_msg, args)


        def assert_router(composer: Composer):
            from cilantro.protocol.states.decorators import StateInput
            from cilantro.messages.reactor.reactor_command import ReactorCommand
            cb = ReactorCommand.create_callback(callback=StateInput.REQUEST, envelope=request_env, header=dealer_id)
            composer.manager.router.route_callback.assert_called_with(cb)

        dealer_id = vk1
        dealer_sk = sk1
        router_sk = sk2
        router_vk = vk2

        request_env = random_envelope(sk=dealer_sk)
        reply_msg = random_msg()

        dealer = MPComposer(name='DEALER', sk=sk1, config_fn=config_dealer, assert_fn=assert_dealer)
        router = MPComposer(config_fn=config_router, assert_fn=assert_router, name='ROUTER', sk=router_sk)

        dealer.add_dealer(vk=router_vk)
        router.add_router(vk=router_vk)

        time.sleep(5.0)

        dealer.send_request_env(vk=router_vk, envelope=request_env)

        self.start()

    # def test_req_reply_1_1_1_timeout(self):
    #     """
    #     Tests request/reply 1_1_1 with a timeout and a late reply
    #     """
    #     def config_router(composer: Composer):
    #         def reply(*args, **kwargs):  # do i need the *args **kwargs ??
    #             time.sleep(timeout_duration * 1.5)
    #             composer.send_reply(message=reply_msg, request_envelope=request_env)
    #
    #         composer.interface.router = MagicMock()
    #         composer.interface.router.route_callback.side_effect = reply
    #         return composer
    #
    #     def config_dealer(composer: Composer):
    #         composer.interface.router = MagicMock()
    #         return composer
    #
    #     def assert_dealer(composer: Composer):
    #         cb = ReactorCommand.create_callback(callback=StateInput.TIMEOUT, envelope=request_env)
    #         composer.interface.router.route_callback.assert_any_call(cb)
    #
    #     def assert_router(composer: Composer):
    #         cb = ReactorCommand.create_callback(callback=StateInput.REQUEST, envelope=request_env, header=dealer_id)
    #         composer.interface.router.route_callback.assert_called_once_with(cb)
    #
    #     timeout_duration = 0.5
    #
    #     dealer_id = vk1
    #     dealer_sk = sk1
    #     router_sk = sk2
    #     router_url = URLS[1]
    #
    #     request_env = random_envelope(sk=dealer_sk)
    #     reply_msg = random_msg()
    #
    #     dealer = MPComposer(name='DEALER', sk=sk1, config_fn=config_dealer, assert_fn=assert_dealer)
    #     router = MPComposer(config_fn=config_router, assert_fn=assert_router, name='ROUTER', sk=router_sk)
    #
    #     dealer.add_dealer(url=router_url)
    #     router.add_router(url=router_url)
    #
    #     time.sleep(0.2)
    #
    #     dealer.send_request_env(url=router_url, envelope=request_env, timeout=timeout_duration)
    #
    #     self.start()


if __name__ == '__main__':
    unittest.main()
