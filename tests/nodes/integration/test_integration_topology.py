from cilantro import Constants
from cilantro.utils.test import MPGod, MPMasternode, MPWitness, MPTestCase, vmnet_test
from unittest.mock import patch, call, MagicMock
from cilantro.utils.test.god import *
from cilantro.nodes import Masternode, Witness, Delegate
from cilantro.nodes.masternode.masternode import *
from cilantro.protocol.statemachine.decorators import StateInput
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

    @vmnet_test
    def test_masternode_receives_std_tx(self):
        """
        Tests that a Masternode properly receives a standard TXs from clients via its POST endpoint
        """
        def config_mn(mn: Masternode):
            assert mn.state == MNRunState, "wtf current state is {}".format(mn.state)

            run_state = mn.states[MNRunState]
            run_state.recv_tx = MagicMock()

            return mn

        def assert_mn(mn: Masternode):
            run_state = mn.states[MNRunState]
            run_state.recv_tx.assert_has_calls([call(tx1), call(tx2)], any_order=True)

        mn_url = Constants.Testnet.Masternode.InternalUrl
        mn_sk = Constants.Testnet.Masternode.Sk

        tx1 = God.create_std_tx(FALCON, DAVIS, 210)
        tx2 = God.create_std_tx(STU, FALCON, 150)

        masternode = MPMasternode(name='Masternode', config_fn=config_mn, assert_fn=assert_mn, sk=mn_sk, url=mn_url)

        time.sleep(0.25)  # give masternode time to get his web server ready

        God.send_tx(tx1)
        God.send_tx(tx2)

        self.start()

    def test_masternode_witness_pubsub(self):
        """
        Tests that a Masternode publishes transactions to the witnesses
        """
        pass


