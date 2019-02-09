from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-2.json')
from cilantro.constants.testnet import *
from cilantro.constants.test_suites import CI_FACTOR
from cilantro.protocol.comm.socket_auth import SocketAuth
from cilantro.utils.test.mp_test_case import MPTestCase, vmnet_test, CILANTRO_PATH
from cilantro.utils.test.mp_testables import MPPubSubAuth
from cilantro.storage.vkbook import VKBook
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
    config_file = '{}/cilantro/vmnet_configs/cilantro-nodes-4.json'.format(CILANTRO_PATH)

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

        BLOCK = False
        time.sleep(1*CI_FACTOR)

        pub1 = MPPubSubAuth(sk=PUB1_SK, name='PUB1', block_until_rdy=BLOCK)
        pub2 = MPPubSubAuth(sk=PUB2_SK, name='PUB2', block_until_rdy=BLOCK)
        sub = MPPubSubAuth(config_fn=config_sub, assert_fn=assert_sub, sk=SUB1_SK, name='SUB', block_until_rdy=True)

        time.sleep(5*CI_FACTOR)

        pub1.add_pub_socket(ip=pub1.ip, secure=True)
        pub2.add_pub_socket(ip=pub2.ip, secure=True)

        sub.add_sub_socket(secure=True)
        sub.connect_sub(vk=PUB1_VK)
        sub.connect_sub(vk=PUB2_VK)

        time.sleep(8*CI_FACTOR)  # Allow time for VK lookup

        pub1.send_pub(msg1)
        pub2.send_pub(msg2)

        self.start(timeout=10*CI_FACTOR)


if __name__ == '__main__':
    unittest.main()
