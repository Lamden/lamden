from vmnet.test.base import *
import cilantro.constants.nodes
import unittest, time

def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper

def run_mn():
    TEST_DUR = 90
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.utils.test.mp_testables import MPMasternode
    from cilantro.constants.testnet import TESTNET_MASTERNODES
    import os, time
    import logging

    log = get_logger("MasternodeRunner")
    log.important3("Test starting")

    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(logging.DEBUG)
    overwrite_logger_level(21)

    sk = TESTNET_MASTERNODES[0]['sk']
    mn = MPMasternode(signing_key=sk)

    log.important3("Sleeping for {} seconds before tearing down".format(TEST_DUR))
    time.sleep(TEST_DUR)
    mn.teardown()


def run_witness(slot_num):
    TEST_DUR = 90
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.constants.testnet import TESTNET_WITNESSES
    from cilantro.utils.test.mp_testables import MPWitness
    import os, time
    import logging

    log = get_logger("WitnessRunner")
    log.important3("Test starting")

    # overwrite_logger_level(logging.WARNING)
    overwrite_logger_level(21)

    w_info = TESTNET_WITNESSES[slot_num]
    w_info['ip'] = os.getenv('HOST_IP')

    witness = MPWitness(signing_key=w_info['sk'])

    log.important3("Sleeping for {} seconds before tearing down".format(TEST_DUR))
    time.sleep(TEST_DUR)
    witness.teardown()


def run_delegate(slot_num):
    TEST_DUR = 90
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.constants.testnet import TESTNET_DELEGATES
    from cilantro.utils.test.mp_testables import MPDelegate
    import os, time
    import logging

    log = get_logger("DelegateRunner")
    log.important3("Test starting")
    # overwrite_logger_level(logging.WARNING)
    overwrite_logger_level(21)

    d_info = TESTNET_DELEGATES[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    delegate = MPDelegate(signing_key=d_info['sk'])

    log.important3("Sleeping for {} seconds before tearing down".format(TEST_DUR))
    time.sleep(TEST_DUR)
    delegate.teardown()


def dump_it(volume, delay=30):
    from cilantro.utils.test import God
    from cilantro.logger import get_logger, overwrite_logger_level
    import logging

    overwrite_logger_level(logging.WARNING)
    God.dump_it(volume=volume, delay=delay)


class TestPerformanceDump(BaseNetworkTestCase):

    VOLUME = 200  # Number of transactions to dump

    testname = 'dump_it'
    setuptime = 5
    compose_file = 'cilantro-bootstrap.yml'

    @vmnet_test(run_webui=True)
    def test_dump(self):

        # Bootstrap master
        self.execute_python('masternode', run_mn, async=True, profiling='c')

        # Bootstrap witnesses
        for i, nodename in enumerate(self.groups['witness']):
            self.execute_python(nodename, wrap_func(run_witness, i), async=True, profiling='c')

        # Bootstrap delegates
        for i, nodename in enumerate(self.groups['delegate']):
            self.execute_python(nodename, wrap_func(run_delegate, i), async=True, profiling='c')

        self.execute_python('mgmt', wrap_func(dump_it, volume=self.VOLUME, delay=20), async=True, profiling='c')

        input("Enter any key to terminate")

if __name__ == '__main__':
    unittest.main()
