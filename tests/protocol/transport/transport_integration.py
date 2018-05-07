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


def random_envelope():
    sk, vk = ED25519Wallet.new()
    tx = StandardTransactionBuilder.random_tx()
    sender = 'me'
    return Envelope.create_from_message(message=tx, signing_key=sk, sender_id=sender)


# TODO -- support multiple classes mp_testable? or is this sketch
@mp_testable(Composer)
class MPComposer(MPTesterBase):
    @classmethod
    def build_obj(cls, sk, sender_id) -> tuple:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mock_sm = MagicMock(spec=StateMachine)
        # router = Router(mock_sm)
        router = MagicMock()

        reactor = ReactorInterface(router=router, loop=loop)
        composer = Composer(interface=reactor, signing_key=sk, sender_id=sender_id)

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
            composer.interface._run_callback = MagicMock()
            return composer
            # reactor._run_callback = MagicMock()
            # return reactor

        def run_assertions(composer: Composer):
            callback = ReactorCommand.create_callback(callback=ROUTE_CALLBACK, envelope=env)
            composer.interface._run_callback.assert_called_once_with(callback)
            # raise Exception("get rekt")

        env = random_envelope()

        sub = MPComposer(config_fn=configure, assert_fn=run_assertions, name='** SUB',
                         sender_id='** SUB', sk=sk1)
        pub = MPComposer(name='++ PUB', sender_id='++ PUB', sk=sk2)

        sub.add_sub(url=URL, filter=FILTER)
        pub.add_pub(url=URL)

        time.sleep(0.2)

        pub.send_pub_env(filter=FILTER, envelope=env)

        self.start()

        # test
        # self.execute_python('node_1', something_silly, async=True)
        # end tests

        # add_sub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=URL,
        #                                         filter=FILTER)
        # add_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=URL)
        # send_pub_cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__,
        #                                          envelope=env, filter=FILTER)
        #
        # sub.send_cmd(add_sub_cmd)
        # pub.send_cmd(add_pub_cmd)
        # time.sleep(0.2)  # To allow time for subs to connect to pub before pub sends data
        # pub.send_cmd(send_pub_cmd)

    def test_req_reply_1_1_1(self):
        """
        Tests request/reply 1_1_1
        """
        def configure(composer: Composer):
            composer.interface._run_callback = MagicMock()
            return composer

        def run_assertions(composer: Composer):
            cb = ReactorCommand.create_callback(callback=ROUTE_REQ_CALLBACK, envelope=env, header=dealer_id)
            composer.interface._run_callback.assert_called_once_with(cb)

        dealer_url = URLS[0]
        dealer_id = vk1
        router_url = URLS[1]

        env = random_envelope()

        dealer = MPComposer(name='DEALER', sender_id='DEALER', sk=sk1)
        router = MPComposer(config_fn=configure, assert_fn=run_assertions, name='ROUTER', sender_id='ROUTER', sk=sk2)

        dealer.add_dealer(url=router_url, id=dealer_id)
        router.add_router(url=router_url)

        time.sleep(0.2)

        dealer.send_request_env(url=router_url, envelope=env)

        self.start()