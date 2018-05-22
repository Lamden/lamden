from cilantro import Constants
from cilantro.utils.test import MPGod, MPMasternode, MPWitness
from cilantro.utils.test import MPTestCase
from unittest.mock import patch, call, MagicMock
from cilantro.utils.test.god import *
from cilantro.nodes import Masternode, Witness, Delegate
import time


"""
Here we do integration tests on our network topology. We spin up nodes on the VM, and ensure that they can talk
to each other how we expect them to.
"""

W = Constants.Protocol.Wallets
sk1, vk1 = W.new()
sk2, vk2 = W.new()
sk3, vk3 = W.new()
sk4, vk4 = W.new()
FILTERS = ['FILTER_' + str(i) for i in range(100)]
URLS = ['tcp://127.0.0.1:' + str(i) for i in range(9000, 9999, 10)]


class TopologyIntegrationTest(MPTestCase):

    def test_masternode_http_request(self):
        """
        Tests that a Masternode properly receives an HTTP request on its web server
        """
        def config_mn(mn: Masternode):
            # TODO implement
            return mn

        def assert_mn(mn: Masternode):
            # TODO implement
            raise Exception("lol get rekt u noob")

        masternode = MPMasternode(name='Masternode', config_fn=config_mn, assert_fn=assert_mn, sk=sk1, url=URLS[0])

        time.sleep(0.5)

        God.send_tx(STU, FALCON, 120)


        self.start()


