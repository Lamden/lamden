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


class TestPubSubSecure(MPTestCase):

    @vmnet_test
    def test_pubsub_2_pub_1_sub_auth(self):
        def assert_sub(test_obj):
            from unittest.mock import call
            expected_frames = [
                call([b'', msg1]),
                call([b'', msg2])
            ]
            test_obj.handle_sub.assert_has_calls(expected_frames, any_order=True)

        msg1 = b'*falcon1 noise*'
        msg2 = b'*falcon2 noise*'

        pub1 = MPPubSubAuth(sk=PUB1_SK, name='PUB1')
        pub2 = MPPubSubAuth(sk=PUB2_SK, name='PUB2')
        sub = MPPubSubAuth(config_fn=config_sub, assert_fn=assert_sub, sk=SUB1_SK, name='SUB')

        pub1.add_pub_socket(ip=pub1.ip, secure=True)
        pub2.add_pub_socket(ip=pub2.ip, secure=True)

        sub.add_sub_socket(secure=True)
        sub.connect_sub(vk=PUB1_VK)
        sub.connect_sub(vk=PUB2_VK)

        time.sleep(5)  # Allow time for VK lookup

        pub1.send_pub(msg1)
        pub2.send_pub(msg2)

        self.start()

    @vmnet_test
    def test_pubsub_1_pub_1_sub_mixed_auth_unsecure(self):
        def assert_sub(test_obj):
            from unittest.mock import call
            expected_frames = [
                call([b'', msg1]),
                call([b'', msg2])
            ]
            test_obj.handle_sub.assert_has_calls(expected_frames, any_order=True)

        msg1 = b'*falcon1 noise*'
        msg2 = b'*falcon2 noise*'

        pub1 = MPPubSubAuth(sk=PUB1_SK, name='PUB1')
        pub2 = MPPubSubAuth(sk=PUB2_SK, name='PUB2')
        sub = MPPubSubAuth(config_fn=config_sub, assert_fn=assert_sub, sk=SUB1_SK, name='SUB')

        pub1.add_pub_socket(ip=pub1.ip, secure=True)
        pub2.add_pub_socket(ip=pub2.ip, secure=False)

        sub.add_sub_socket(secure=True, socket_key='sub1')
        sub.add_sub_socket(secure=False, socket_key='sub2')
        sub.connect_sub(vk=PUB1_VK, socket_key='sub1')
        sub.connect_sub(vk=PUB2_VK, socket_key='sub2')

        time.sleep(8)  # Allow time for VK lookup

        pub1.send_pub(msg1)
        pub2.send_pub(msg2)

        self.start()

if __name__ == '__main__':
    unittest.main()
