from cilantro.logger.base import get_logger
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.base.base import MessageBase
from cilantro.protocol import wallet

from cilantro.protocol.comm.socket_manager import SocketManager
from cilantro.protocol.comm.lsocket import LSocket

import asyncio
import zmq.asyncio
import time

from vmnet.testcase import BaseNetworkTestCase
import unittest, time, random, vmnet, cilantro
from cilantro.utils.test.mp_test_case import vmnet_test
from os.path import join, dirname


def run_pub():
    from cilantro.utils.test.pubsub_auth import PubSubAuthTester
    from cilantro.protocol.overlay.daemon import OverlayServer
    from cilantro.constants.testnet import TESTNET_MASTERNODES
    from cilantro.utils.lprocess import LProcess
    import os

    sk = TESTNET_MASTERNODES[0]['sk']

    overlay_proc = LProcess(target=OverlayServer, kwargs={'sk': sk})
    overlay_proc.start()

    t = PubSubAuthTester(signing_key=sk, name='Pub')

    # Create 1 pub and start publishing
    t.add_pub_socket(ip=os.getenv('HOST_IP'))
    t.start_publishing()

    t.start()

def run_sub():
    from cilantro.utils.test.pubsub_auth import PubSubAuthTester
    from cilantro.protocol.overlay.daemon import OverlayServer, OverlayClient
    from cilantro.utils.lprocess import LProcess
    from cilantro.constants.testnet import TESTNET_DELEGATES
    from cilantro.constants.testnet import TESTNET_MASTERNODES
    import os

    sk = TESTNET_DELEGATES[0]['sk']
    pub_vk = TESTNET_MASTERNODES[0]['vk']

    overlay_proc = LProcess(target=OverlayServer, kwargs={'sk': sk})
    overlay_proc.start()

    t = PubSubAuthTester(signing_key=sk, name='SUB')

    # Create 1 sub
    t.add_sub_socket()
    t.connect_sub(vk=pub_vk)

    t.start()


class TestDump(BaseNetworkTestCase):

    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-nodes.json')

    @vmnet_test(run_webui=True)
    def test_dump(self):

        self.execute_python('node_1', run_pub)
        self.execute_python('node_2', run_sub)

        input("Enter any key to terminate")


if __name__ == '__main__':
    unittest.main()

