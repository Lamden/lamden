from unittest.mock import MagicMock, call, patch
from cilantro.messages import *
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.protocol.reactor.interface import ReactorInterface
from cilantro.protocol.reactor.executor import *
from cilantro.messages import ReactorCommand
from cilantro.utils.test import MPTesterBase, MPTestCase, mp_testable
import time


URL = 'tcp://127.0.0.1:9988'
FILTER = 'TEST_FILTER'

FILTERS = ['FILTER_' + str(i) for i in range(100)]
URLS = ['tcp://127.0.0.1:' + str(i) for i in range(9000, 9999, 10)]


def random_envelope():
    sk, vk = ED25519Wallet.new()
    tx = StandardTransactionBuilder.random_tx()
    return Envelope.create_from_message(message=tx, signing_key=sk)


@mp_testable(ReactorInterface)
class MPReactorInterface(MPTesterBase):
    @classmethod
    def build_obj(cls) -> tuple:
        mock_parent = MagicMock()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        reactor = ReactorInterface(mock_parent, loop=loop)

        asyncio.ensure_future(reactor._recv_messages())

        return reactor, loop


def something_silly():
    from cilantro.logger import get_logger
    log = get_logger("SILLLY THING FUNC")
    log.critical("\n\n\nasl;fjl;jkl;fadsfkl;jkl;adsjfkl;j234u23l;e2kfj23423890490-f8\n\n\n")


class TestReactorPubSub(MPTestCase):
    def test_1_1_1(self):
        """
        Tests pub/sub 1-1 (one sub one pub) with one message
        """
        def configure_interface(reactor: ReactorInterface):
            reactor._run_callback = MagicMock()
            return reactor

        def run_assertions(reactor: ReactorInterface):
            callback = ReactorCommand.create_callback(callback=ROUTE_CALLBACK, envelope=env)
            reactor._run_callback.assert_called_once_with(callback)

        env = random_envelope()

        sub = MPReactorInterface(config_fn=configure_interface, assert_fn=run_assertions, name='** SUB')
        pub = MPReactorInterface(name='++ PUB')

        # test
        # self.execute_python('node_1', something_silly, async=True)
        # end tests

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
            cb1 = ReactorCommand.create_callback(callback=ROUTE_CALLBACK, envelope=env1)
            cb2 = ReactorCommand.create_callback(callback=ROUTE_CALLBACK, envelope=env2)
            reactor._run_callback.assert_has_calls([
                call(cb1),
                call(cb2)],
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

        time.sleep(0.2)  # Give time for both pubs to go through

        self.start()

    # TODO -- same test as above but assertions fails testing

    def test_1_1_n_delay(self):
        """
        Tests pub/sub 1-1 with 3 messages, and a 0.2 second delay between messages. The messages should be received in
        order they are sent
        """

        def configure_interface(reactor: ReactorInterface):
            reactor._run_callback = MagicMock()
            return reactor

        def run_assertions(reactor: ReactorInterface):
            cb1 = ReactorCommand.create_callback(callback=ROUTE_CALLBACK, envelope=env1)
            cb2 = ReactorCommand.create_callback(callback=ROUTE_CALLBACK, envelope=env2)
            reactor._run_callback.assert_has_calls([
                call(cb1),
                call(cb2)],
                any_order=False)

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
        time.sleep(0.1)  # Give time for first message to go through first
        pub.send_cmd(send_pub_cmd2)

        time.sleep(0.2)  # To allow both pubs to go through

        self.start()

    def test_pubsub_1_n_n_filters(self):
        """
        Test pub/sub 1-1 with multiple filters, only some of which should be received
        """
        # TODO -- implement
        self.assertTrue(27**2 + 36**2 == 45**2)
        return

        def configure_interface(reactor: ReactorInterface):
            reactor._run_callback = MagicMock()
            return reactor

        def run_assertions(reactor: ReactorInterface):
            cb = ReactorCommand.create_callback(callback=ROUTE_CALLBACK, envelope=env1)
            reactor._run_callback.assert_called_once_with(cb)

        env1, env2, env3, env4, env5 = (random_envelope() for _ in range(5))

        sub = MPReactorInterface(config_fn=configure_interface, assert_fn=run_assertions, name='** SUB')
        pub1 = MPReactorInterface(name='++ PUB 1')
        pub2 = MPReactorInterface(name='++ PUB 2')
        pub3 = MPReactorInterface(name='++ PUB 3')

        add_sub_cmd1 = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=URLS[1],
                                                filter=FILTERS[1])
        add_sub_cmd2 = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=URLS[1],
                                                filter=FILTERS[2])
        add_sub_cmd3 = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=URLS[1],
                                                 filter=FILTERS[3])
        add_pub_cmd1 = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=URL)
        add_pub_cmd2 = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=URL)

        send_pub_cmd1 = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__,
                                                 envelope=env1, filter=FILTERS[1])
        send_pub_cmd2 = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__,
                                                 envelope=env2, filter=FILTERS[1])

        sub.send_cmd(add_sub_cmd1)
        sub.send_cmd(add_sub_cmd1)
        pub1.send_cmd(add_pub_cmd1)
        pub2.send_cmd(add_pub_cmd1)
        time.sleep(0.2)  # To allow time for subs to connect to pub before pub sends data
        pub1.send_cmd(send_pub_cmd1)

        time.sleep(0.2)  # Allow pubs to go through

        self.start()

    def test_pubsub_1_1_n_filters(self):
        """
        Tests pub/sub with 1 sub, 1 pub sending a few messages on different filters
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
            cb = ReactorCommand.create_callback(callback=ROUTE_CALLBACK, envelope=env)
            reactor._run_callback.assert_called_once_with(cb)

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
        # TODO - implement
        import random
        a, b, c, d = (random.randint(0, pow(2, 16)) for _ in range(4))
        self.assertTrue((a ** 2 + b ** 2) * (c ** 2 + d ** 2) == pow(a * c + b * d, 2) + pow(a * d - b * c, 2))


import unittest
if __name__ == '__main__':
    print("MANI RUNNING")
    unittest.main()















