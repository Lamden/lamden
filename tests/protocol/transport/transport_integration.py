from cilantro import Constants
from cilantro.utils.test import MPTesterBase, MPTestCase, mp_testable
from unittest.mock import patch, call, MagicMock
from cilantro.protocol.transport import Router, Composer
from cilantro.protocol.reactor import ReactorInterface
from cilantro.messages import *
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.protocol.statemachine import StateMachine
from cilantro.protocol.reactor.executor import *
import asyncio
import time


W = Constants.Protocol.Wallets
sk1, vk1 = W.new()
sk2, vk2 = W.new()
sk3, vk3 = W.new()
sk4, vk4 = W.new()

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


# TODO -- support multiple classes mp_testable? or is this sketch
@mp_testable(Composer)
class MPComposer(MPTesterBase):
    @classmethod
    def build_obj(cls, sk) -> tuple:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mock_sm = MagicMock(spec=StateMachine)
        # router = Router(mock_sm)
        router = MagicMock()

        reactor = ReactorInterface(router=router, loop=loop)
        composer = Composer(interface=reactor, signing_key=sk)

        asyncio.ensure_future(reactor._recv_messages())

        return composer, loop


# TODO -- move this to a test util module or something
@mp_testable(ReactorInterface)
# class MPReactorInterface(MPTesterBase):
#     @classmethod
#     def build_obj(cls) -> tuple:
#         mock_parent = MagicMock(spec=Router)
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
#
#         reactor = ReactorInterface(mock_parent, loop=loop)
#
#         return reactor, loop



class TransportIntegrationTest(MPTestCase):
    def test_pubsub_1_1_1(self):
        """
        Tests pub/sub 1-1 (one sub one pub) with one message
        """
        def configure(composer: Composer):
            composer.interface.router = MagicMock()
            return composer

        def run_assertions(composer: Composer):
            callback = ReactorCommand.create_callback(callback=ROUTE_CALLBACK, envelope=env)
            composer.interface.router.route_callback.assert_called_once_with(callback)

        env = random_envelope()

        sub = MPComposer(config_fn=configure, assert_fn=run_assertions, name='** SUB', sk=sk1)
        pub = MPComposer(name='++ PUB', sk=sk2)

        sub.add_sub(url=URL, filter=FILTER)
        pub.add_pub(url=URL)

        time.sleep(0.2)

        pub.send_pub_env(filter=FILTER, envelope=env)

        self.start()

    def test_pubsub_1_1_2_mult_filters(self):
        """
        Tests pub/sub 1-1 (one sub one pub) with 2 message each on a different filter
        """
        def configure(composer: Composer):
            composer.interface.router = MagicMock()
            return composer

        def run_assertions(composer: Composer):
            cb1 = ReactorCommand.create_callback(callback=ROUTE_CALLBACK, envelope=env1)
            cb2 = ReactorCommand.create_callback(callback=ROUTE_CALLBACK, envelope=env2)
            composer.interface.router.route_callback.assert_has_calls([call(cb1), call(cb2)], any_order=True)

        env1 = random_envelope()
        env2 = random_envelope()
        filter1 = FILTERS[0]
        filter2 = FILTERS[1]

        sub = MPComposer(config_fn=configure, assert_fn=run_assertions, name='** SUB', sk=sk1)
        pub = MPComposer(name='++ PUB', sk=sk2)

        sub.add_sub(url=URL, filter=filter2)
        sub.add_sub(url=URL, filter=filter1)
        pub.add_pub(url=URL)

        time.sleep(0.2)

        pub.send_pub_env(filter=filter1, envelope=env1)
        pub.send_pub_env(filter=filter2, envelope=env2)

        self.start()


    # TODO FIX THIS (figure out how to validate env.messsage = reply_msg)..ithink we can use "call_args_list"
    def test_req_reply_1_1_1(self):
        """
        Tests request/reply 1_1_1
        """
        def config_router(composer: Composer):
            def reply(*args, **kwargs):  # do i need the *args **kwargs ??
                composer.send_reply(message=reply_msg, request_envelope=request_env)

            composer.interface.router = MagicMock()
            composer.interface.router.route_callback.side_effect = reply
            return composer

        def config_dealer(composer: Composer):
            composer.interface.router = MagicMock()
            return composer

        def assert_dealer(composer: Composer):
            def assert_correct_args(*args, **kwargs):
                log = get_logger("ASSERT_DEALER")
                log.critical("ASSERT_CORRECT_ARGS called with args={}, and kwargs={}".format(args, kwargs))

                assert len(args) == 1, "Expected one arg to be passed into route_callback (the envelope)"

                env = args[0]

                assert env.message == reply_msg, "Reply Envelope message != to reply message!!! OH MAYNE"

                raise Exception("get rekt from the inside kid!!!")  # this is not reking the test through...hmm

            composer.interface.router.route_callback.side_effect = assert_correct_args

            raise Exception("get rekt u scrub")

        def assert_router(composer: Composer):
            cb = ReactorCommand.create_callback(callback=ROUTE_REQ_CALLBACK, envelope=request_env, header=dealer_id)
            composer.interface.router.route_callback.assert_called_once_with(cb)

        dealer_id = vk1
        dealer_sk = sk1
        router_sk = sk2
        router_url = URLS[1]

        request_env = random_envelope(sk=dealer_sk)
        reply_msg = random_msg()

        dealer = MPComposer(name='DEALER', sk=sk1, config_fn=config_dealer, assert_fn=assert_dealer)
        router = MPComposer(config_fn=config_router, assert_fn=assert_router, name='ROUTER', sk=router_sk)

        dealer.add_dealer(url=router_url)
        router.add_router(url=router_url)

        time.sleep(0.2)

        dealer.send_request_env(url=router_url, envelope=request_env)

        self.start()

    def test_req_reply_1_1_1_timeout(self):
        """
        Tests request/reply 1_1_1 with a timeout and a late reply
        """
        def config_router(composer: Composer):
            def reply(*args, **kwargs):  # do i need the *args **kwargs ??
                time.sleep(timeout_duration * 1.5)
                composer.send_reply(message=reply_msg, request_envelope=request_env)

            composer.interface.router = MagicMock()
            composer.interface.router.route_callback.side_effect = reply
            return composer

        def config_dealer(composer: Composer):
            composer.interface.router = MagicMock()
            return composer

        def assert_dealer(composer: Composer):
            cb = ReactorCommand.create_callback(callback=ROUTE_TIMEOUT_CALLBACK, envelope=request_env)
            composer.interface.router.route_callback.assert_any_call(cb)

        def assert_router(composer: Composer):
            cb = ReactorCommand.create_callback(callback=ROUTE_REQ_CALLBACK, envelope=request_env, header=dealer_id)
            composer.interface.router.route_callback.assert_called_once_with(cb)

        timeout_duration = 0.5

        dealer_id = vk1
        dealer_sk = sk1
        router_sk = sk2
        router_url = URLS[1]

        request_env = random_envelope(sk=dealer_sk)
        reply_msg = random_msg()

        dealer = MPComposer(name='DEALER', sk=sk1, config_fn=config_dealer, assert_fn=assert_dealer)
        router = MPComposer(config_fn=config_router, assert_fn=assert_router, name='ROUTER', sk=router_sk)

        dealer.add_dealer(url=router_url)
        router.add_router(url=router_url)

        time.sleep(0.2)

        dealer.send_request_env(url=router_url, envelope=request_env, timeout=timeout_duration)

        self.start()