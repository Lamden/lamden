from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-4.json')
from cilantro.constants.testnet import *
from cilantro.constants.test_suites import CI_FACTOR

from cilantro.utils.test.mp_test_case import MPTestCase, vmnet_test
from cilantro.utils.test.mp_testables import MPPubSubAuth
import unittest, time


PUB1_SK, PUB1_VK = TESTNET_MASTERNODES[0]['sk'], TESTNET_MASTERNODES[0]['vk']
PUB2_SK, PUB2_VK = TESTNET_MASTERNODES[1]['sk'], TESTNET_MASTERNODES[1]['vk']
SUB1_SK, SUB1_VK = TESTNET_DELEGATES[0]['sk'], TESTNET_DELEGATES[0]['vk']
SUB2_SK, SUB2_VK = TESTNET_DELEGATES[1]['sk'], TESTNET_DELEGATES[1]['vk']


def config_sub(test_obj):
    from unittest.mock import MagicMock
    test_obj.handle_sub = MagicMock()
    return test_obj


class TestPubSubBadActor(MPTestCase):

    @vmnet_test
    def test_pubsub_1_pub_1_sub_mixed_auth_unsecure_bad_sub(self):
        def assert_sub(test_obj):
            test_obj.handle_sub.assert_not_called()

        msg = b'*falcon noise*'

        BLOCK = False
        time.sleep(1*CI_FACTOR)

        pub = MPPubSubAuth(sk=PUB1_SK, name='PUB1', block_until_rdy=BLOCK)
        sub = MPPubSubAuth(config_fn=config_sub, assert_fn=assert_sub, sk=SUB1_SK, name='SUB', block_until_rdy=BLOCK)

        time.sleep(15*CI_FACTOR)

        pub.add_pub_socket(ip=pub.ip, secure=True)

        sub.add_sub_socket(secure=False, socket_key='sub1')
        sub.connect_sub(vk=PUB1_VK, socket_key='sub1')

        time.sleep(15*CI_FACTOR)  # Allow time for VK lookup

        pub.send_pub(msg)
        time.sleep(2)

        self.start(timeout=20*CI_FACTOR)

    # @vmnet_test
    # def test_pubsub_1_pub_1_sub_mixed_auth_unsecure_bad_pub(self):
    #     pass #TODO
    #
    # @vmnet_test
    # def test_pubsub_1_pub_1_sub_mixed_auth_unsecure_bad_sub_sk(self):
    #     pass #TODO
    #
    # @vmnet_test
    # def test_pubsub_1_pub_1_sub_mixed_auth_unsecure_bad_pub_sk(self):
    #     pass #TODO


if __name__ == '__main__':
    unittest.main()
