from cilantro.utils.test.mp_test_case import MPTestCase, vmnet_test
from cilantro.utils.test.mp_testables import MPPubSubAuth
import unittest, time

from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES

PUB1_SK, PUB1_VK = TESTNET_MASTERNODES[0]['sk'], TESTNET_MASTERNODES[0]['vk']
PUB2_SK, PUB2_VK = TESTNET_MASTERNODES[1]['sk'], TESTNET_MASTERNODES[1]['vk']
SUB1_SK, SUB1_VK = TESTNET_DELEGATES[0]['sk'], TESTNET_DELEGATES[0]['vk']
SUB2_SK, SUB2_VK = TESTNET_DELEGATES[1]['sk'], TESTNET_DELEGATES[1]['vk']


def config_sub(test_obj):
    from unittest.mock import MagicMock
    test_obj.handle_sub = MagicMock()
    return test_obj


class TestReactorOverlay(MPTestCase):

    @vmnet_test
    def test_pubsub_1_pub_2_sub_unauth(self):
        def assert_sub(test_obj):
            # from cilantro.logger.base import get_logger
            # log = get_logger("Sub Assertatorizer")
            # log.important("Sub got callbacks: {}".format(test_obj.handle_sub.call_args_list))
            expected_frames = [b'', msg]  # Filter is b''
            test_obj.handle_sub.assert_called_with(expected_frames)

        msg = b'ass'

        pub = MPPubSubAuth(sk=PUB1_SK, name='PUB')
        sub1 = MPPubSubAuth(config_fn=config_sub, assert_fn=assert_sub, sk=SUB1_SK, name='SUB')
        sub2 = MPPubSubAuth(config_fn=config_sub, assert_fn=assert_sub, sk=SUB1_SK, name='SUB')

        pub.add_pub_socket(ip=pub.ip)

        for sub in (sub1, sub2):
            sub.add_sub_socket()
            sub.connect_sub(vk=PUB1_VK)

        time.sleep(5)  # Allow time for VK lookup

        pub.send_pub(msg)

        self.start()

    # @vmnet_test
    # def test_pubsub_1_pub_2_sub_auth(self):
    #     pass
    #
    # @vmnet_test
    # def test_pubsub_2_pub_1_sub_auth(self):
    #     pass
    #
    # @vmnet_test
    # def test_pubsub_2_pub_2_sub_auth(self):
    #     pass
    #
    # @vmnet_test
    # def test_pubsub_2_pub_2_sub_mixed_auth_unauth(self):
    #     pass


if __name__ == '__main__':
    unittest.main()