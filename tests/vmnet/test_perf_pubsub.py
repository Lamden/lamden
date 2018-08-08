from vmnet.test.base import *
import unittest


def publisher():
    SLEEP_TIME = 1
    MAX_TIME = 10
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.utils.test import MPComposer
    from cilantro.messages.transaction.contract import ContractTransactionBuilder
    from cilantro.constants.testnet import TESTNET_DELEGATES
    import time, os

    log = get_logger("Publisher")
    sub_info = TESTNET_DELEGATES[1]
    sub_info['ip'] = os.getenv('HOST_IP')

    d_info = TESTNET_DELEGATES[0]
    d_info['ip'] = os.getenv('HOST_IP')

    pub = MPComposer(sk=d_info['sk'])

    # Publish on this node's own IP
    pub.add_pub(os.getenv('HOST_IP'))

    log.important("Starting experiment, sending messages every {} seconds for a total of {} seconds".format(SLEEP_TIME, MAX_TIME))
    elapsed_time = 0

    while elapsed_time < MAX_TIME:
        log.notice("Sending pub")
        msg = ContractTransactionBuilder.random_currency_tx()
        pub.send_pub_msg(filter='0', message=msg)

        time.sleep(SLEEP_TIME)
        elapsed_time += SLEEP_TIME

    pub.teardown()
    log.important("Done with experiment!")


def subscriber():
    SLEEP_TIME = 1
    MAX_TIME = 20
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.utils.test import MPComposer
    from cilantro.constants.testnet import TESTNET_DELEGATES
    import time, os

    log = get_logger("Subscriber")

    d_info = TESTNET_DELEGATES[1]
    d_info['ip'] = os.getenv('HOST_IP')

    pub_info = TESTNET_DELEGATES[0]
    pub_info['ip'] = os.getenv('HOST_IP')

    sub = MPComposer(sk=d_info['sk'])
    sub.add_sub(filter='0', vk=pub_info['vk'])

    log.important2("Starting Subscriber, and exiting after {} seconds".format(MAX_TIME))
    time.sleep(MAX_TIME)

    sub.teardown()
    log.important2("Done with experiment!")


class TestPerformancePubSub(BaseNetworkTestCase):

    testname = 'composer'
    setuptime = 6
    compose_file = 'cilantro-nodes.yml'

    @vmnet_test(run_webui=True)
    def test_network(self):
        self.execute_python('node_1', publisher, async=True, profiling=True)
        self.execute_python('node_2', subscriber, async=True, profiling=True)

        input("Press any key to end test")


if __name__ == '__main__':
    unittest.main()
