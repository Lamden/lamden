from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-4.json')
from cilantro.constants.testnet import *

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


class TestPubSubSecure(MPTestCase):

    @vmnet_test
    def test_pubsub_1_pub_2_sub_unsecure(self):
        def assert_sub(test_obj):
            expected_frames = [b'', msg]  # Filter is b''
            test_obj.handle_sub.assert_called_with(expected_frames)

        msg = b'*falcon noise*'

        pub = MPPubSubAuth(sk=PUB1_SK, name='PUB')
        sub1 = MPPubSubAuth(config_fn=config_sub, assert_fn=assert_sub, sk=SUB1_SK, name='SUB1')
        sub2 = MPPubSubAuth(config_fn=config_sub, assert_fn=assert_sub, sk=SUB1_SK, name='SUB2')

        pub.add_pub_socket(ip=pub.ip)

        for sub in (sub1, sub2):
            sub.add_sub_socket()
            sub.connect_sub(vk=PUB1_VK)

        time.sleep(5)  # Allow time for VK lookup

        pub.send_pub(msg)

        self.start()

    @vmnet_test
    def test_pubsub_1_pub_2_sub_auth(self):
        def assert_sub(test_obj):
            expected_frames = [b'', msg]  # Filter is b''
            test_obj.handle_sub.assert_called_with(expected_frames)

        msg = b'*falcon noise*'

        pub = MPPubSubAuth(sk=PUB1_SK, name='PUB')
        sub1 = MPPubSubAuth(config_fn=config_sub, assert_fn=assert_sub, sk=SUB1_SK, name='SUB1')
        sub2 = MPPubSubAuth(config_fn=config_sub, assert_fn=assert_sub, sk=SUB1_SK, name='SUB2')

        pub.add_pub_socket(ip=pub.ip, secure=True)

        for sub in (sub1, sub2):
            sub.add_sub_socket(secure=True)
            sub.connect_sub(vk=PUB1_VK)

        time.sleep(5)  # Allow time for VK lookup

        pub.send_pub(msg)

        self.start()


if __name__ == '__main__':
    unittest.main()
