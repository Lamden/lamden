from vmnet.test.base import *
from vmnet.test.util import *
import unittest

def send_four_tx():
    from cilantro.testnet_config.tx_builder import send_tx, DAVIS, STU
    send_tx(DAVIS,STU,1)
    send_tx(DAVIS,STU,2)
    send_tx(DAVIS,STU,3)
    send_tx(DAVIS,STU,4)

class TestCilantroConsensus(BaseNetworkTestCase):
    testname = 'consensus'
    compose_file = 'cilantro-m-w-d.yml'
    setuptime = 15
    def test_in_consensus(self):
        self.execute_python('mgmt', send_four_tx)
        # for node in ['delegate_5', 'delegate_6', 'delegate_7']:
        #     in_consensus = False
        #     for l in self.content[node]:
        #         if 'Delegate in consensus!' in l:
        #             in_consensus = True
        #             break
        #     self.assertTrue(in_consensus, '{} failed: Delegates are not in consensus'.format(node))

if __name__ == '__main__':
    unittest.main()
