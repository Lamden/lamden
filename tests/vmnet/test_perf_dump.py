from vmnet.testcase import BaseNetworkTestCase
import unittest, time, random, vmnet, cilantro
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test


def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper


def run_mn():
    TEST_DUR = 170
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.utils.test.god import countdown
    from cilantro.utils.test.mp_testables import MPMasternode
    from cilantro.constants.testnet import TESTNET_MASTERNODES
    import os, time
    import logging

    log = get_logger("MasternodeRunner")
    log.important3("Test starting")

    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(logging.DEBUG)
    overwrite_logger_level(21)
    # overwrite_logger_level(10)

    sk = TESTNET_MASTERNODES[0]['sk']
    mn = MPMasternode(signing_key=sk)

    log.important3("Sleeping for {} seconds before tearing down".format(TEST_DUR))
    countdown(TEST_DUR, "Tearing down in {} seconds...", log, status_update_freq=10)
    time.sleep(TEST_DUR)
    mn.teardown()

    log.success("EXPERIMENT OVER!!!")


def run_witness(slot_num):
    TEST_DUR = 170
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.utils.test.god import countdown
    from cilantro.constants.testnet import TESTNET_WITNESSES
    from cilantro.utils.test.mp_testables import MPWitness
    import os, time
    import logging

    log = get_logger("WitnessRunner")
    log.important3("Test starting")

    # overwrite_logger_level(logging.WARNING)
    overwrite_logger_level(21)
    # overwrite_logger_level(10)

    w_info = TESTNET_WITNESSES[slot_num]
    w_info['ip'] = os.getenv('HOST_IP')

    witness = MPWitness(signing_key=w_info['sk'])

    log.important3("Sleeping for {} seconds before tearing down".format(TEST_DUR))
    countdown(TEST_DUR, "Tearing down in {} seconds...", log, status_update_freq=10)
    # time.sleep(TEST_DUR)
    witness.teardown()

    log.success("EXPERIMENT OVER!!!")


def run_delegate(slot_num):
    TEST_DUR = 170
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.utils.test.god import countdown
    from cilantro.constants.testnet import TESTNET_DELEGATES
    from cilantro.utils.test.mp_testables import MPDelegate
    import os, time
    import logging

    log = get_logger("DelegateRunner")
    log.important3("Test starting")
    # overwrite_logger_level(logging.WARNING)
    overwrite_logger_level(21)
    # overwrite_logger_level(10)


    d_info = TESTNET_DELEGATES[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    delegate = MPDelegate(signing_key=d_info['sk'])

    log.important3("Sleeping for {} seconds before tearing down".format(TEST_DUR))
    countdown(TEST_DUR, "Tearing down in {} seconds...", log, status_update_freq=10)
    # time.sleep(TEST_DUR)
    delegate.teardown()

    log.success("EXPERIMENT OVER!!!")


def dump_it(volume, delay=20):
    from cilantro.utils.test import God
    from cilantro.logger import get_logger, overwrite_logger_level
    import logging

    overwrite_logger_level(logging.WARNING)
    God.dump_it(volume=volume, delay=delay)


class TestPerformanceDump(BaseNetworkTestCase):

    VOLUME = 1000  # Number of transactions to dump
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-bootstrap.json')
    PROFILE_TYPE = 'c'

    @vmnet_test(run_webui=True)
    def test_dump(self):

        # Bootstrap master
        self.execute_python('masternode', run_mn, async=True, profiling=self.PROFILE_TYPE)

        # Bootstrap witnesses
        for i, nodename in enumerate(self.groups['witness']):
            self.execute_python(nodename, wrap_func(run_witness, i), async=True, profiling=self.PROFILE_TYPE)

        # Bootstrap delegates
        for i, nodename in enumerate(self.groups['delegate']):
            self.execute_python(nodename, wrap_func(run_delegate, i), async=True, profiling=self.PROFILE_TYPE)

        self.execute_python('mgmt', wrap_func(dump_it, volume=self.VOLUME, delay=20), async=True, profiling=self.PROFILE_TYPE)

        input("Enter any key to terminate")


if __name__ == '__main__':
    unittest.main()
