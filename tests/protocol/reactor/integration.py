
from unittest.mock import MagicMock, call, patch
from cilantro.messages import *
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.reactor.core import CHILD_RDY_SIG
from cilantro.protocol.reactor.executor import *
from cilantro.messages import ReactorCommand
from cilantro.utils.test import MPTesterBase, MPTestCase, mp_testable
import time


URL = 'tcp://127.0.0.1:9988'
FILTER = 'TEST_FILTER'


def random_envelope():
    sk, vk = ED25519Wallet.new()
    tx = StandardTransactionBuilder.random_tx()
    sender = 'me'
    return Envelope.create_from_message(message=tx, signing_key=sk, sender_id=sender)


@mp_testable(ReactorInterface)
class MPReactorInterface(MPTesterBase):
    @classmethod
    def build_obj(cls) -> tuple:
        mock_parent = MagicMock()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        reactor = ReactorInterface(mock_parent, loop=loop)

        return reactor, loop


class TestReactorInterfacePubSub(MPTestCase):
    def test_1_1_1(self):
        """
        Tests pub/sub 1-1 (one sub one pub) with one message
        """
        def configure_interface(reactor: ReactorInterface):
            reactor._run_callback = MagicMock()
            return reactor

        def run_assertions(reactor: ReactorInterface):
            callback = 'route'
            data = env.serialize()
            reactor._run_callback.assert_called_once_with(callback, data)

        env = random_envelope()

        sub = MPReactorInterface(config_fn=configure_interface, assert_fn=run_assertions, name='** SUB')
        pub = MPReactorInterface(name='++ PUB')

        add_sub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=URL,
                                                filter=FILTER)
        add_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=URL)
        send_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__,
                                                 envelope=env, filter=FILTER)

        sub.send_cmd(add_sub_cmd)
        pub.send_cmd(add_pub_cmd)
        time.sleep(0.2)  # To allow time for subs to connect to pub before pub sends data
        pub.send_cmd(send_pub_cmd)

        self.start()

    def test_1_1_n(self):
        """
        Tests pub/sub 1-1 with 2 messages (any order with no delay in sends)
        """
        def configure_interface(reactor: ReactorInterface):
            reactor._run_callback = MagicMock()
            return reactor

        def run_assertions(reactor: ReactorInterface):
            callback = 'route'
            reactor._run_callback.assert_has_calls([
                                                    call(callback, env1.serialize()),
                                                    call(callback, env2.serialize())],
                                                    any_order=True)

        env1 = random_envelope()
        env2 = random_envelope()

        sub = MPReactorInterface(config_fn=configure_interface, assert_fn=run_assertions, name='** SUB')
        pub = MPReactorInterface(name='++ PUB')

        add_sub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=URL,
                                                filter=FILTER)
        add_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=URL)
        send_pub_cmd1 = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__,
                                                 envelope=env1, filter=FILTER)
        send_pub_cmd2 = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__,
                                                  envelope=env2, filter=FILTER)

        sub.send_cmd(add_sub_cmd)
        pub.send_cmd(add_pub_cmd)
        time.sleep(0.2)
        pub.send_cmd(send_pub_cmd1)
        pub.send_cmd(send_pub_cmd2)

        time.sleep(0.2)  # To allow both pubs to go through

        self.start()

    def test_1_1_n_delay(self):
        """
        Tests pub/sub 1-1 with 3 messages, and a 0.2 second delay between messages. The messages should be received in
        order they are sent
        """

        def configure_interface(reactor: ReactorInterface):
            reactor._run_callback = MagicMock()
            return reactor

        def run_assertions(reactor: ReactorInterface):
            callback = 'route'
            reactor._run_callback.assert_has_calls([
                call(callback, env1.serialize()),
                call(callback, env2.serialize())],
                any_order=True)

        env1 = random_envelope()
        env2 = random_envelope()

        sub = MPReactorInterface(config_fn=configure_interface, assert_fn=run_assertions, name='** SUB')
        pub = MPReactorInterface(name='++ PUB')

        add_sub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=URL,
                                                filter=FILTER)
        add_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=URL)
        send_pub_cmd1 = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__,
                                                  envelope=env1, filter=FILTER)
        send_pub_cmd2 = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__,
                                                  envelope=env2, filter=FILTER)

        sub.send_cmd(add_sub_cmd)
        pub.send_cmd(add_pub_cmd)
        time.sleep(0.2)
        pub.send_cmd(send_pub_cmd1)
        pub.send_cmd(send_pub_cmd2)

        time.sleep(0.2)  # To allow both pubs to go through

        self.start()


    def test_pubsub_1_1_n_filters(self):
        """
        Test pub/sub 1-1 with multiple filters, only some of which should be received
        """
        # TODO -- implement
        self.assertTrue('cats' == 'cats')

    def test_pubsub_1_n_n_filters(self):
        """
        Tests pub/sub with 1 sub, 3ish pubs each sending a few messages on different filters
        :return:
        """
        # TODO -- implement
        self.assertTrue(2 + 2 == 4)

    def test_subpub_1_n_1(self):
        """
        Tests sub/pub with 1 publisher and 3 subs, with one message
        """
        def configure_interface(reactor: ReactorInterface):
            reactor._run_callback = MagicMock()
            return reactor

        def run_assertions(reactor: ReactorInterface):
            callback = 'route'
            data = env.serialize()
            reactor._run_callback.assert_called_once_with(callback, data)

        env = random_envelope()

        sub1 = MPReactorInterface(config_fn=configure_interface, assert_fn=run_assertions, name='** SUB1')
        sub2 = MPReactorInterface(config_fn=configure_interface, assert_fn=run_assertions, name='** SUB2')
        sub3 = MPReactorInterface(config_fn=configure_interface, assert_fn=run_assertions, name='** SUB3')
        pub = MPReactorInterface(name='++ PUB')

        add_sub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=URL,
                                                filter=FILTER)
        add_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=URL)
        send_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__,
                                                 envelope=env, filter=FILTER)

        sub1.send_cmd(add_sub_cmd)
        sub2.send_cmd(add_sub_cmd)
        sub3.send_cmd(add_sub_cmd)
        pub.send_cmd(add_pub_cmd)
        time.sleep(0.2)
        pub.send_cmd(send_pub_cmd)

        self.start()

    def test_pubsub_n_n_n_filters(self):
        """
        THE ULTIMATE TEST

        Im talkin 4ish subs, 5ish pubs, 15ish messages, 7ish filters. A nice beefy network topology to assert on.
        """
        import random
        a, b, c, d = (random.randint(0, pow(2,16)) for _ in range(4))
        self.assertTrue((a**2 + b**2) * (c**2 + d**2) == pow(a*c + b*d, 2) + pow(a*d - b*c, 2))























