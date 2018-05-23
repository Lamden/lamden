from cilantro import Constants
from cilantro.utils.test import MPGod, MPMasternode, MPWitness
from cilantro.utils.test import MPTestCase
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

    def test_masternode_receives_std_tx(self):
        """
        Tests that a Masternode properly receives a standard TXs from users
        """
        def config_mn(mn: Masternode):
            assert mn.state == MNRunState, "what the fuck current state is {}".format(mn.state)
            # Mock the recv_tx method on run state
            run_state = mn.states[MNRunState]

            MNRunState.recv_tx = MagicMock()

            # assert mn.state is run_state, "these things shoudl be teh same obj, wtf if they arent"

            # input_handler = run_state._get_input_handler(tx1, StateInput.INPUT)

            # self.log.critical("\n\n got input handler: {} and 'intuitive handler' {} and maybe the same handler {}\n\n".format(input_handler, run_state.recv_tx, MNRunState.recv_tx))

            # self.log.critical("\n\n\n DIR:\n{} \n\n\n".format(dir(run_state)))

            # run_state.stupid_effect = MagicMock()

            return mn

        def assert_mn(mn: Masternode):
            # run_state = mn.states[MNRunState]
            MNRunState.recv_tx.assert_has_calls([call(tx1), call(tx2)], any_order=True)
            # raise Exception("lol get rekt u noob")

        mn_url = Constants.Testnet.Masternode.InternalUrl
        mn_sk = Constants.Testnet.Masternode.Sk

        tx1 = God.create_std_tx(FALCON, DAVIS, 210)
        tx2 = God.create_std_tx(STU, FALCON, 150)

        masternode = MPMasternode(name='Masternode', config_fn=config_mn, assert_fn=assert_mn, sk=mn_sk, url=mn_url)

        time.sleep(0.25)  # give masternode time to get his web server ready

        God.send_tx(tx1)
        God.send_tx(tx2)

        self.start()


