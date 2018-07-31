from vmnet.test.base import *
from cilantro.utils.test import MPComposer
import unittest, time, random
from cilantro.constants.testnet import delegates

def publisher():
    SLEEP_TIME = 1
    MAX_TIME = 10
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.utils.test import MPComposer
    from cilantro.messages.transaction.standard import StandardTransactionBuilder
    import time, os

    log = get_logger("Publisher")
    sub_info = delegates[1]
    sub_info['ip'] = os.getenv('HOST_IP')

    d_info = delegates[0]
    d_info['ip'] = os.getenv('HOST_IP')

    pub = MPComposer(sk=d_info['sk'])

    # Publish on this node's own IP
    pub.add_pub(os.getenv('HOST_IP'))

    log.critical("Starting experiment, sending messages every {} seconds for a total of {} seconds".format(SLEEP_TIME, MAX_TIME))
    elapsed_time = 0

    while elapsed_time < MAX_TIME:
        log.info("Sending pub")
        msg = StandardTransactionBuilder.random_tx()
        pub.send_pub_msg(filter='0', message=msg)

        time.sleep(SLEEP_TIME)
        elapsed_time += SLEEP_TIME

    pub.teardown()
    log.critical("Done with experiment!")


def subscriber():
    SLEEP_TIME = 1
    MAX_TIME = 10
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.utils.test import MPComposer
    import time, os

    log = get_logger("Subscriber")

    d_info = delegates[1]
    d_info['ip'] = os.getenv('HOST_IP')

    pub_info = delegates[0]
    pub_info['ip'] = os.getenv('HOST_IP')

    sub = MPComposer(sk=d_info['sk'])
    sub.add_sub(filter='0', vk=pub_info['vk'])

    log.critical("Starting Subscriber, and exiting after {} seconds".format(SLEEP_TIME))
    time.sleep(MAX_TIME)

    sub.teardown()
    log.critical("Done with experiment!")


class TestNetworkPerformance(BaseNetworkTestCase):

    EXPECTED_TRANSACTION_RATE = 0.1  # Avg transaction/second. lambda parameter in Poission distribution
    MODEL_AS_POISSON = False

    testname = 'composer'
    setuptime = 10
    compose_file = 'cilantro-nodes.yml'

    @vmnet_test(run_webui=True)
    def test_network(self):
        self.execute_python('node_1', publisher, async=True, profiling=True)
        self.execute_python('node_2', subscriber, async=True, profiling=True)

        input("Press any key to end test")


if __name__ == '__main__':
    unittest.main()
