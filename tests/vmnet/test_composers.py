from vmnet.test.base import *
import unittest, time
from cilantro.constants.testnet import delegates

def publisher():
    from cilantro.logger import get_logger
    from cilantro import Constants
    from cilantro.utils.test import MPComposer
    from cilantro.messages import StandardTransactionBuilder
    import time, os, sys

    log = get_logger("Publisher")
    sub_info = delegates[1]
    sub_info['ip'] = os.getenv('HOST_IP')

    d_info = delegates[0]
    d_info['ip'] = os.getenv('HOST_IP')

    pub = MPComposer(sk=d_info['sk'])

    # Publish on this node's own IP
    pub.add_pub(os.getenv('HOST_IP'))

    for i in range(100):
        log.critical("Sending pub")
        msg = StandardTransactionBuilder.random_tx()
        time.sleep(0.1)
        pub.send_pub_msg(filter='0', message=msg)

    log.critical("Pub Done")
    sys.exit(0)
    exit


def subscriber():
    from cilantro.logger import get_logger
    from cilantro.utils.test import MPComposer
    import time, os, sys

    log = get_logger("Sub")

    d_info = delegates[1]
    d_info['ip'] = os.getenv('HOST_IP')

    pub_info = delegates[0]
    pub_info['ip'] = os.getenv('HOST_IP')

    sub = MPComposer(sk=d_info['sk'])
    sub.add_sub(filter='0', vk=pub_info['vk'])

    log.critical("Sub sleeping")
    time.sleep(26)
    log.critical("Sub done. Exiting.")

    sys.exit(0)
    exit


class TestNetworkPerformance(BaseNetworkTestCase):

    EXPECTED_TRANSACTION_RATE = 0.1  # Avg transaction/second. lambda parameter in Poission distribution
    MODEL_AS_POISSON = False

    testname = 'pump_it'
    setuptime = 10
    compose_file = 'cilantro-nodes.yml'

    @vmnet_test(run_webui=True)
    def test_network(self):
        self.execute_python('node_1', publisher, async=True)
        self.execute_python('node_2', subscriber, async=True)

        time.sleep(10)
        #input("Press any key to end test")
        exit


if __name__ == '__main__':
    unittest.main()
