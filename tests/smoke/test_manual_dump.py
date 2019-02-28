NETWORK_SIZE = '2-2-2'

MN_LOG_LVL = 11
WITNESS_LOG_LVL = 30
DELEGATE_LOG_LVL = 1# 11
SENECA_LOG_LVL = 11

# Set ENABLE_BAD_ACTORS to TRUE to enable periodic consensus failures
ENABLE_BAD_ACTORS = False
BAD_ACTOR_SET = {1}  # The indices of delegates who shall misbehave and periodically send bad SubBlockContender
BAD_SB_SET = {1}  # The indices of the sub-blocks to send bad SubBlockContenders for

RESET_DB = False


from cilantro_ee.utils.test.testnet_config import set_testnet_config
set_testnet_config('{}.json'.format(NETWORK_SIZE))

from vmnet.testcase import BaseNetworkTestCase
import unittest, time, random, vmnet, cilantro_ee, os
from os.path import join, dirname
from cilantro_ee.utils.test.mp_test_case import vmnet_test
from cilantro_ee.utils.test.god import God
from cilantro_ee.logger.base import get_logger
from cilantro_ee.utils.test.node_runner import *
from cilantro_ee.logger import get_logger, overwrite_logger_level
import logging, os, shutil, time
from cilantro_ee.constants.system_config import *


if os.getenv('USE_LOCAL_SENECA', '0') != '0':
    log = get_logger("SenecaCopier")
    user_sen_path = os.getenv('SENECA_PATH', None)
    assert user_sen_path, "If USE_LOCAL_SENECA env var is set, SENECA_PATH env var must also be set!"

    import cilantro_ee
    venv_sen_path = cilantro_ee.__path__[0] + '/../venv/lib/python3.6/site-packages/seneca'

    assert os.path.isdir(venv_sen_path), "Expect virtual env seneca at path {}".format(venv_sen_path)
    assert os.path.isdir(user_sen_path), "Expect user seneca at path {}".format(user_sen_path)

    log.debugv("Removing venv seneca at path {}".format(venv_sen_path))
    shutil.rmtree(venv_sen_path)

    log.notice("Copying user seneca path {} to venv packages at path {}".format(user_sen_path, venv_sen_path))
    shutil.copytree(user_sen_path, venv_sen_path)
    log.notice("Done copying")


class TestManualDump(BaseNetworkTestCase):

    NUM_BLOCKS = 2
    VOLUME = TRANSACTIONS_PER_SUB_BLOCK * NUM_SB_PER_BLOCK * NUM_BLOCKS  # Number of transactions to dump
    config_file = join(dirname(cilantro_ee.__path__[0]), 'vmnet_configs', 'cilantro_ee-{}-bootstrap.json'.format(NETWORK_SIZE))
    PROFILE_TYPE = None

    @vmnet_test(run_webui=True)
    def test_dump(self):
        log = get_logger("Dumpatron")
        cmd = 'docker container stop $(docker container ls -a -q -f name=delegate_8)'
        cmd1 = 'docker kill $(docker container ls -a -q -f name=delegate_8)'

        log.important("PORTS: {}".format(self.ports))

        # Bootstrap master
        for i, nodename in enumerate(self.groups['masternode']):
            self.execute_python(nodename, God.run_mn(i, log_lvl=MN_LOG_LVL, nonce_enabled=False, reset_db=RESET_DB),
                                async=True, profiling=self.PROFILE_TYPE)

        # Bootstrap witnesses
        for i, nodename in enumerate(self.groups['witness']):
            self.execute_python(nodename, God.run_witness(i, log_lvl=WITNESS_LOG_LVL, reset_db=RESET_DB), async=True,
                                profiling=self.PROFILE_TYPE)

        # Bootstrap delegates
        for i, nodename in enumerate(self.groups['delegate']):
            if ENABLE_BAD_ACTORS and i in BAD_ACTOR_SET:
                self.execute_python(nodename, God.run_delegate(i, log_lvl=DELEGATE_LOG_LVL, seneca_log_lvl=SENECA_LOG_LVL,
                                    reset_db=RESET_DB, bad_actor=True, bad_sb_set=BAD_SB_SET), async=True,
                                    profiling=self.PROFILE_TYPE)
            else:
                self.execute_python(nodename, God.run_delegate(i, log_lvl=DELEGATE_LOG_LVL, seneca_log_lvl=SENECA_LOG_LVL,
                                    reset_db=RESET_DB), async=True, profiling=self.PROFILE_TYPE)

        while True:
            user_input = input("Enter an integer representing the # of transactions to dump, or 'x' to quit.")

            if user_input.lower() == 's':
                log.important("stoping delegate 5")
                os.system(cmd)
                time.sleep(5)
                os.system(cmd1)

            if user_input.lower() == 'c':
                log.important("Testing catchup start delegate 8")
                self.execute_python('delegate_8', wrap_func(run_delegate, 3), async=True, profiling=self.PROFILE_TYPE)

            if user_input.lower() == 'x':
                log.important("Termination input detected. Breaking")
                break

            vol = int(user_input) if user_input.isdigit() else self.VOLUME
            log.important3("Dumpatron dumping {} transactions!".format(vol))
            self.execute_python('mgmt', God.dump_it(volume=vol), async=True, profiling=self.PROFILE_TYPE)


if __name__ == '__main__':
    unittest.main()
