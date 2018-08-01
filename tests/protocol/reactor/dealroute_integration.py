from unittest.mock import MagicMock, call, patch
# from cilantro.messages import *
from cilantro.messages.transaction.standard import StandardTransactionBuilder
from cilantro.protocol.wallet import Wallet
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.reactor.executor import *
from cilantro.messages.reactor.reactor_command import ReactorCommand
from cilantro.utils.test import MPTesterBase, MPTestCase, mp_testable
import time


URL = 'tcp://127.0.0.1:9988'
FILTER = 'TEST_FILTER'

FILTERS = ['FILTER_' + str(i) for i in range(100)]
URLS = ['tcp://127.0.0.1:' + str(i) for i in range(9000, 9999, 10)]


# TODO -- move this to a test util module or something
def random_envelope():
    sk, vk = Wallet.new()
    tx = StandardTransactionBuilder.random_tx()
    sender = 'me'
    return Envelope.create_from_message(message=tx, signing_key=sk, sender_id=sender)


# TODO -- move this to a test util module or something
@mp_testable(ReactorInterface)
class MPReactorInterface(MPTesterBase):
    @classmethod
    def build_obj(cls) -> tuple:
        mock_parent = MagicMock()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        reactor = ReactorInterface(mock_parent, loop=loop)

        return reactor, loop


def config_reactor(reactor: ReactorInterface):
    reactor._run_callback = MagicMock()
    return reactor


class TestReactorDealerRouter(MPTestCase):

    def test_req_1_1_1(self):
        """
        Tests dealer router 1/1 (1 dealer, 1 router) with 1 message request (dealer sends router 1 message)
        """
        def run_assertions(reactor: ReactorInterface):
            cb = ReactorCommand.create_callback(callback=ROUTE_REQ_CALLBACK, envelope=env, header=DEALER_ID)
            reactor._run_callback.assert_called_once_with(cb)

        DEALER_URL = URLS[0]
        DEALER_ID = "id-" + DEALER_URL  # irl this would a node's vk
        ROUTER_URL = URLS[1]

        env = random_envelope()

        dealer = MPReactorInterface(name='DEALER')
        router = MPReactorInterface(config_fn=config_reactor, assert_fn=run_assertions, name='ROUTER')

        add_dealer = ReactorCommand.create_cmd(class_name=DealerRouterExecutor.__name__,
                                               func_name=DealerRouterExecutor.add_dealer.__name__,
                                               url=ROUTER_URL, id=DEALER_ID)
        add_router = ReactorCommand.create_cmd(class_name=DealerRouterExecutor.__name__,
                                               func_name=DealerRouterExecutor.add_router.__name__,
                                               url=ROUTER_URL)
        request = ReactorCommand.create_cmd(class_name=DealerRouterExecutor.__name__,
                                            func_name=DealerRouterExecutor.request.__name__,
                                            url=ROUTER_URL,  envelope=env)

        dealer.send_cmd(add_dealer)
        router.send_cmd(add_router)

        time.sleep(0.2)
        dealer.send_cmd(request)

        self.start()

    def test_req_reply_1_1_1(self):
        """
        Tests a request/reply round trip between dealer and router.
        """
        def config_dealer(reactor: ReactorInterface):
            reactor._run_callback = MagicMock()
            return reactor

        def config_router(reactor: ReactorInterface):
            def reply_effect(*args, **kwargs):
                # log = get_logger("ASSERT ROUTER SIDE EFFECT WTIH")
                # log.critical("\n\n sending reply command... \n\n")
                reactor.send_cmd(reply)
                dealer.send_cmd(reply)

            reactor._run_callback = MagicMock()
            reactor._run_callback.side_effect = reply_effect
            return reactor

        def assert_dealer(reactor: ReactorInterface):
            cb = ReactorCommand.create_callback(callback=ROUTE_CALLBACK, envelope=rep_env)
            reactor._run_callback.assert_called_once_with(cb)

        def assert_router(reactor: ReactorInterface):
            cb = ReactorCommand.create_callback(callback=ROUTE_REQ_CALLBACK, envelope=req_env, header=DEALER_ID)
            reactor._run_callback.assert_called_once_with(cb)
            # reactor._run_callback.side_effect = reply_effect

        DEALER_URL = URLS[0]
        DEALER_ID = "id-" + DEALER_URL  # irl this would a node's vk
        ROUTER_URL = URLS[1]

        req_env = random_envelope()
        rep_env = random_envelope()

        add_dealer = ReactorCommand.create_cmd(class_name=DealerRouterExecutor.__name__,
                                               func_name=DealerRouterExecutor.add_dealer.__name__,
                                               url=ROUTER_URL, id=DEALER_ID)
        add_router = ReactorCommand.create_cmd(class_name=DealerRouterExecutor.__name__,
                                               func_name=DealerRouterExecutor.add_router.__name__,
                                               url=ROUTER_URL)

        request = ReactorCommand.create_cmd(class_name=DealerRouterExecutor.__name__,
                                            func_name=DealerRouterExecutor.request.__name__,
                                            url=ROUTER_URL, envelope=req_env)
        reply = ReactorCommand.create_cmd(class_name=DealerRouterExecutor.__name__,
                                          func_name=DealerRouterExecutor.reply.__name__,
                                          id=DEALER_ID, envelope=rep_env)

        dealer = MPReactorInterface(name='DEALER', config_fn=config_dealer, assert_fn=assert_dealer)
        router = MPReactorInterface(config_fn=config_router, assert_fn=assert_router, name='ROUTER')

        dealer.send_cmd(add_dealer)
        router.send_cmd(add_router)
        time.sleep(0.2)

        dealer.send_cmd(request)

        self.start()

    def test_req_reply_1_1_n(self):
        """
        Tests mutiple request/reply round trips between dealer and router.
        """
        self.assertEqual('hi', 'hi')

    def test_req_1_n_1(self):
        """
        Tests req from 1 dealer to 2 routers.
        """
        def run_assertions(reactor: ReactorInterface):
            cb = ReactorCommand.create_callback(callback=ROUTE_REQ_CALLBACK, envelope=env, header=DEALER_ID)
            reactor._run_callback.assert_called_once_with(cb)

        DEALER_URL = URLS[0]
        DEALER_ID = "id-" + DEALER_URL  # irl this would a node's vk
        ROUTER1_URL = URLS[0]
        ROUTER2_URL = URLS[1]

        env = random_envelope()

        dealer = MPReactorInterface(name='DEALER')
        router1 = MPReactorInterface(config_fn=config_reactor, assert_fn=run_assertions, name='ROUTER 1')
        router2 = MPReactorInterface(config_fn=config_reactor, assert_fn=run_assertions, name='ROUTER 2')

        add_dealer1 = ReactorCommand.create_cmd(class_name=DealerRouterExecutor.__name__,
                                                func_name=DealerRouterExecutor.add_dealer.__name__,
                                                url=ROUTER1_URL, id=DEALER_ID)
        add_dealer2 = ReactorCommand.create_cmd(class_name=DealerRouterExecutor.__name__,
                                                func_name=DealerRouterExecutor.add_dealer.__name__,
                                                url=ROUTER2_URL, id=DEALER_ID)
        add_router1 = ReactorCommand.create_cmd(class_name=DealerRouterExecutor.__name__,
                                                func_name=DealerRouterExecutor.add_router.__name__,
                                                url=ROUTER1_URL)
        add_router2 = ReactorCommand.create_cmd(class_name=DealerRouterExecutor.__name__,
                                                func_name=DealerRouterExecutor.add_router.__name__,
                                                url=ROUTER2_URL)
        request1 = ReactorCommand.create_cmd(class_name=DealerRouterExecutor.__name__,
                                             func_name=DealerRouterExecutor.request.__name__,
                                             url=ROUTER1_URL,  envelope=env)
        request2 = ReactorCommand.create_cmd(class_name=DealerRouterExecutor.__name__,
                                             func_name=DealerRouterExecutor.request.__name__,
                                             url=ROUTER2_URL, envelope=env)

        dealer.send_cmd(add_dealer1)
        dealer.send_cmd(add_dealer2)
        router1.send_cmd(add_router1)
        router2.send_cmd(add_router2)

        time.sleep(0.2)
        dealer.send_cmd(request1)
        dealer.send_cmd(request2)

        self.start()

    # TODO -- test above, but don't send something to one of the routers and assert an error

    # TODO -- test 1_n_1_n round trip req/reply

    # TODO -- test timeouts

    # TODO -- test n-n-n

    # TODO -- test n-1-1

    # TODO -- tests for just replies (router --> dealer) i.e. no request from dealer first
