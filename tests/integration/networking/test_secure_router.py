from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-4.json')
from cilantro.constants.testnet import *

from cilantro.utils.test.mp_test_case import MPTestCase, vmnet_test, CILANTRO_PATH
from cilantro.utils.test.mp_testables import MPRouterAuth
import unittest, time


PUB1_SK, PUB1_VK = TESTNET_MASTERNODES[0]['sk'], TESTNET_MASTERNODES[0]['vk']
PUB2_SK, PUB2_VK = TESTNET_MASTERNODES[1]['sk'], TESTNET_MASTERNODES[1]['vk']


def config_node(test_obj):
    from unittest.mock import MagicMock
    test_obj.handle_router_msg = MagicMock()
    return test_obj


class TestRouterSecure(MPTestCase):
    config_file = '{}/cilantro/vmnet_configs/cilantro-nodes-2.json'.format(CILANTRO_PATH)

    @vmnet_test
    def test_one_bind_other_connect(self):
        def assert_router(test_obj):
            test_obj.handle_router_msg.assert_called_once()

        msg = b'*falcon noise*'

        router1 = MPRouterAuth(sk=PUB1_SK, name='ROUTER 1', config_fn=config_node, assert_fn=assert_router)
        router2 = MPRouterAuth(sk=PUB2_SK, name='ROUTER 2')

        for r in (router1, router2):
            r.create_router_socket(identity=r.ip.encode(), secure=True)

        router1.bind_router_socket(ip=router1.ip)
        router2.connect_router_socket(vk=PUB1_VK)

        # Give time for VK lookup
        time.sleep(5)

        router2.send_msg(id_frame=router1.ip.encode(), msg=b'hi from router 2!')

        self.start()

    @vmnet_test
    def test_both_bind(self):
        def assert_router(test_obj):
            test_obj.handle_router_msg.assert_called_once()

        msg = b'*falcon noise*'

        # THIS TEST IS PASSING, BUT SHOULD IT BE? LOOKS LIKE ONLY ONE GET IS GETTING THE MSG

        router1 = MPRouterAuth(sk=PUB1_SK, name='ROUTER 1', config_fn=config_node, assert_fn=assert_router)
        router2 = MPRouterAuth(sk=PUB2_SK, name='ROUTER 2', config_fn=config_node, assert_fn=assert_router)

        for r in (router1, router2):
            r.create_router_socket(identity=r.ip.encode(), secure=True, name='Router-{}'.format(r.ip))
            r.bind_router_socket(ip=r.ip)

        router1.connect_router_socket(vk=PUB2_VK)
        router2.connect_router_socket(vk=PUB1_VK)

        # Give time for VK lookup
        time.sleep(5)

        router2.send_msg(id_frame=router1.ip.encode(), msg=b'hi from router 2!')
        router1.send_msg(id_frame=router2.ip.encode(), msg=b'hi from router 1!')

        self.start()

if __name__ == '__main__':
    unittest.main()
