from cilantro.utils.test.mp_test_case import MPTestCase, vmnet_test
from cilantro.utils.test.mp_testables import MPPubSubAuth
import unittest, time

from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES

PUB1_SK, PUB1_VK = TESTNET_MASTERNODES[0]['sk'], TESTNET_MASTERNODES[0]['vk']
PUB2_SK, PUB2_VK = TESTNET_MASTERNODES[1]['sk'], TESTNET_MASTERNODES[1]['vk']
SUB1_SK, SUB1_VK = TESTNET_DELEGATES[0]['sk'], TESTNET_DELEGATES[0]['vk']
SUB2_SK, SUB2_VK = TESTNET_DELEGATES[1]['sk'], TESTNET_DELEGATES[1]['vk']


class TestReactorOverlay(MPTestCase):

    @vmnet_test
    def test_pubsub_1_pub_2_sub_unauth(self):
        def config_sub(test_obj):
            from unittest.mock import MagicMock
            test_obj.handle_pub = MagicMock()
            return test_obj

        def assert_sub(test_obj):
            from cilantro.logger.base import get_logger
            log = get_logger("Sub Assertatorizer")
            # log.debugv("type of testobj.handle_pub: {}".format(type(test_obj.handle_pub)))
            log.important("Sub got callbacks: {}".format(test_obj.handle_pub.call_args_list))

            i = 10 / 0

        pub = MPPubSubAuth(sk=PUB1_SK, name='PUB')
        sub = MPPubSubAuth(config_fn=config_sub, assert_fn=assert_sub, sk=SUB1_SK, name='SUB')

        # time.sleep(5)  # nap while overlay hooks up ? We shouldnt need this but ur boy is paranoid

        pub.add_pub_socket(ip=pub.ip)

        sub.add_sub_socket()
        sub.connect_sub(vk=PUB1_VK)

        # time.sleep(5)  # for the vk lookup? also should need this but again, i be paranoid af

        pub.start_publishing()

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