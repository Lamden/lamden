from cilantro.utils.test.mp_test_case import MPTestCase, vmnet_test
from cilantro.utils.test.mp_testables import MPComposer
from cilantro.protocol.transport import Composer
from cilantro.messages.transaction.standard import StandardTransactionBuilder
from cilantro.protocol import wallet
from cilantro.messages.envelope.envelope import Envelope
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

    # TODO implement this
    # @vmnet_test
    # def test_pair(self):
    #     def assert_pair_1(composer: Composer):
    #         pass
    #
    #     def assert_pair_2(composer: Composer):
    #         pass
    #
    #     env = random_envelope()
    #     env2 = random_envelope()
    #     port = 8123
    #
    #     pair1 = MPComposer(assert_fn=assert_pair_1, name='[MN1] PAIR1', sk=sk1)
    #     pair2 = MPComposer(assert_fn=assert_pair_2, name='[Delegate1] PAIR2', sk=sk2)
    #
    #     # Take a nap while we wait for overlay to hookup
    #     time.sleep(5)
    #
    #     pair1.bind_pair(port=port)
    #     pair1.connect_pair(port=port, vk=vk1)
    #
    #     time.sleep(2)  # Allow nodes to connect before sending the next command



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

        time.sleep(2)  # Allow nodes to connect before sending the next command

        pub.send_pub_env(filter=FILTER, envelope=env)

        self.start()

    @vmnet_test
    def test_pubsub_n_1_n(self):
        """
        Tests pub/sub with 2 pubs, 1 sub, and multiple messages and the same filter
        """
        def assert_sub(composer: Composer):
            from cilantro.protocol.states.decorators import StateInput
            from unittest.mock import call

            expected_calls = []
            for env in envs:
                expected_calls.append(call(callback=StateInput.INPUT, envelope=env, message=env.message))

            composer.manager.router.route_callback.assert_has_calls(expected_calls, any_order=True)

        envs = [random_envelope() for _ in range(4)]

        sub = MPComposer(assert_fn=assert_sub, name='[MN1] SUB', sk=sk1)
        pub1 = MPComposer(name='[Delegate1] PUB1', sk=sk2)
        pub2 = MPComposer(name='[Delegate2] PUB2', sk=sk3)

        time.sleep(5)  # Take a nap while we wait for overlay to hookup

        sub.add_sub(vk=vk2, filter=FILTER)
        sub.add_sub(vk=vk3, filter=FILTER)

        pub1.add_pub(ip=pub1.ip)
        pub2.add_pub(ip=pub2.ip)

        time.sleep(5.0)  # Allow nodes to connect

        pub1.send_pub_env(filter=FILTER, envelope=envs[0])
        pub1.send_pub_env(filter=FILTER, envelope=envs[1])

        pub2.send_pub_env(filter=FILTER, envelope=envs[2])
        pub2.send_pub_env(filter=FILTER, envelope=envs[3])

        self.start()

    # TODO same test as above, but with multiple filters

    # TODO fix this test
    # @vmnet_test
    # def test_pubsub_n_1_n_removesub(self):
    #     """
    #     Tests pub/sub n-1, with a sub removing a publisher after its first message
    #     """
    #     def assert_sub(composer: Composer):
    #         from cilantro.protocol.states.decorators import StateInput
    #         from unittest.mock import call
    #
    #         expected_calls = []
    #         for env in (env1, env2):
    #             expected_calls.append(call(callback=StateInput.INPUT, envelope=env, message=env.message))
    #
    #         composer.manager.router.route_callback.assert_has_calls(expected_calls, any_order=True)
    #
    #     env1 = random_envelope()
    #     env2 = random_envelope()
    #     env3 = random_envelope()
    #
    #     sub = MPComposer(assert_fn=assert_sub, name='SUB [MN1]', sk=sk1)
    #     pub1 = MPComposer(name='PUB 1 [Delegate1]', sk=sk2)
    #     pub2 = MPComposer(name='PUB 2 [Delegate2]', sk=sk3)
    #
    #     sub.add_sub(vk=vk2, filter=FILTER)  # sub to pub1
    #     sub.add_sub(vk=vk3, filter=FILTER)  # sub to pub2
    #
    #     pub1.add_pub(ip=pub1.ip)  # Pub on its own URL
    #     pub2.add_pub(ip=pub2.ip)  # Pub on its own URL
    #
    #     time.sleep(5.0)
    #
    #     pub1.send_pub_env(filter=FILTER, envelope=env1)
    #     pub2.send_pub_env(filter=FILTER, envelope=env2)
    #
    #     time.sleep(2.0)  # allow messages to go through
    #     sub.remove_sub(vk=vk3)  # unsub to pub2
    #     time.sleep(2.0)  # allow remove_sub_url command to go through
    #
    #     pub2.send_pub_env(filter=FILTER, envelope=env3)  # this should not be recv by sub, as he removed this guy's url
    #
    #     self.start()

    @vmnet_test
    def test_pubsub_1_1_2_mult_filters(self):
        """
        Tests pub/sub 1-1 (one sub one pub) with 2 message each on a different filter
        """
        def run_assertions(composer: Composer):
            from cilantro.protocol.states.decorators import StateInput
            from unittest.mock import call

            expected_calls = []
            for env in (env1, env2):
                expected_calls.append(call(callback=StateInput.INPUT, envelope=env, message=env.message))

            composer.manager.router.route_callback.assert_has_calls(expected_calls, any_order=True)

        env1 = random_envelope()
        env2 = random_envelope()
        filter1 = FILTERS[0]
        filter2 = FILTERS[1]

        sub = MPComposer(assert_fn=run_assertions, name='SUB', sk=sk1)
        pub = MPComposer(name='PUB', sk=sk2)

        time.sleep(5)  # Take a nap while we wait for overlay to hookup

        sub.add_sub(vk=vk2, filter=filter2)
        sub.add_sub(vk=vk2, filter=filter1)
        pub.add_pub(ip=pub.ip)

        time.sleep(3)  # allow time for VK lookups before we start sending things

        # Send 2 envelopes on 2 different filters
        pub.send_pub_env(filter=filter1, envelope=env1)
        pub.send_pub_env(filter=filter2, envelope=env2)

        self.start()

    # TODO fix this
    # @vmnet_test
    # def test_req_reply_1_1_1(self):
    #     """
    #     Tests request/reply 1_1_1
    #     """
    #     def config_router(composer: Composer):
    #         def reply(*args, **kwargs):  # do i need the *args **kwargs ??
    #             composer.send_reply(message=reply_msg, request_envelope=request_env)
    #
    #         composer.manager.router.route_callback.side_effect = reply
    #         return composer
    #
    #     def assert_dealer(composer: Composer):
    #         from cilantro.protocol.states.decorators import StateInput
    #         from unittest.mock import call, ANY
    #
    #         # expected_calls = [call(callback=StateInput.INPUT, envevlope=env, message=env.message)]
    #         # args = composer.manager.router.route_callback.call_args_list
    #         cb = call(callback=StateInput.INPUT, envelope=ANY, message=reply_msg)
    #         composer.manager.router.route_callback.assert_called_with(callback=StateInput.INPUT, envelope=ANY, message=reply_msg)
    #         # composer.manager.router.route_callback.assert_has_calls([cb], any_order=True)
    #         # reply_callback_found = Falsek
    #         # for call in args:
    #         #     if
    #             # callback_cmd = call[0][0]
    #
    #             # DEBUG TODO DELETE
    #             # from cilantro.logger.base import get_logger
    #             # log = get_logger("TEST")
    #             # log.important3("got call {}".format(call))
    #             # END DEBUG
    #
    #             # assert isinstance(callback_cmd, ReactorCommand), "arg of route_callback should be a ReactorCommand"
    #             # if callback_cmd.envelope and callback_cmd.envelope.message == reply_msg:
    #             #     reply_callback_found = True
    #             #     break
    #                 # assert callback_cmd.envelope.message == reply_msg, "Callback's envelope's message should be the reply_msg"
    #         # assert reply_callback_found, "Reply callback {} not found in call args {}".format(reply_msg, args)
    #
    #
    #     def assert_router(composer: Composer):
    #         from cilantro.protocol.states.decorators import StateInput
    #         from unittest.mock import call
    #         cb = call(callback=StateInput.REQUEST, envelope=request_env,
    #                                             message=request_env.message, header=dealer_id)
    #         composer.manager.router.route_callback.assert_called_with(callback=StateInput.REQUEST, envelope=request_env,
    #                                                                   message=request_env.message, header=dealer_id)
    #
    #     dealer_id = vk1
    #     dealer_sk = sk1
    #     router_sk = sk2
    #     router_vk = vk2
    #
    #     request_env = random_envelope(sk=dealer_sk)
    #     reply_msg = random_msg()
    #
    #     dealer = MPComposer(name='DEALER', sk=sk1, assert_fn=assert_dealer)
    #     router = MPComposer(config_fn=config_router, assert_fn=assert_router, name='ROUTER', sk=router_sk)
    #
    #     time.sleep(5)  # allow for overlay to hook up
    #
    #     dealer.add_dealer(vk=router_vk)
    #     router.add_router()
    #
    #     time.sleep(5)
    #
    #     dealer.send_request_env(vk=router_vk, envelope=request_env)
    #
    #     self.start()

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
