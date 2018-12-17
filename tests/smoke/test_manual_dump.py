from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-2.json')

from vmnet.testcase import BaseNetworkTestCase
import unittest, time, random, vmnet, cilantro, os
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test
from cilantro.utils.test.god import God
from cilantro.logger.base import get_logger
from cilantro.utils.test.god import God
from cilantro.logger import get_logger, overwrite_logger_level
import logging, os, shutil, time
from cilantro.constants.system_config import *


if os.getenv('USE_LOCAL_SENECA', '0') != '0':
    log = get_logger("SenecaCopier")
    user_sen_path = os.getenv('SENECA_PATH', None)
    assert user_sen_path, "If USE_LOCAL_SENECA env var is set, SENECA_PATH env var must also be set!"

    import cilantro
    venv_sen_path = cilantro.__path__[0] + '/../venv/lib/python3.6/site-packages/seneca'

    assert os.path.isdir(venv_sen_path), "Expect virtual env seneca at path {}".format(venv_sen_path)
    assert os.path.isdir(user_sen_path), "Expect user seneca at path {}".format(user_sen_path)

    log.debugv("Removing venv seneca at path {}".format(venv_sen_path))
    shutil.rmtree(venv_sen_path)

    log.notice("Copying user seneca path {} to venv packages at path {}".format(user_sen_path, venv_sen_path))
    shutil.copytree(user_sen_path, venv_sen_path)
    log.notice("Done copying")


def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper


def run_mn(slot_num):
    # We must set this env var before we import anything from cilantro
    import os
    os.environ["NONCE_DISABLED"] = "1"

    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.nodes.factory import NodeFactory
    from cilantro.constants.testnet import TESTNET_MASTERNODES

    # NOTE setting the log level below 11 does not work for some reason --davis
    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(21)
    # overwrite_logger_level(11)

    ip = os.getenv('HOST_IP')
    sk = TESTNET_MASTERNODES[slot_num]['sk']
    NodeFactory.run_masternode(ip=ip, signing_key=sk, reset_db=True)


def run_witness(slot_num):
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.nodes.factory import NodeFactory
    from cilantro.constants.testnet import TESTNET_WITNESSES
    import os
    import logging

    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(21)
    # overwrite_logger_level(11)

    w_info = TESTNET_WITNESSES[slot_num]
    w_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_witness(ip=w_info['ip'], signing_key=w_info['sk'], reset_db=True)


def run_delegate(slot_num):
    from cilantro.logger import get_logger, overwrite_logger_level
    from seneca.libs.logger import overwrite_logger_level as sen_overwrite_log
    from cilantro.nodes.factory import NodeFactory
    from cilantro.constants.testnet import TESTNET_DELEGATES
    import os
    import logging

    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level
    sen_overwrite_log(4)  # disable spam only (lvl 5 is debugv)

    d_info = TESTNET_DELEGATES[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_delegate(ip=d_info['ip'], signing_key=d_info['sk'], reset_db=True)


def dump_it(volume, delay=0):
    from cilantro.utils.test.god import God
    from cilantro.logger import get_logger, overwrite_logger_level
    import logging

    overwrite_logger_level(logging.WARNING)
    God.dump_it(volume=volume, delay=delay)


class TestManualDump(BaseNetworkTestCase):

    NUM_BLOCKS = 2
    VOLUME = TRANSACTIONS_PER_SUB_BLOCK * NUM_SB_PER_BLOCK * NUM_BLOCKS  # Number of transactions to dump
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-2-2-2-bootstrap.json')
    PROFILE_TYPE = None

    @vmnet_test(run_webui=True)
    def test_dump(self):
        log = get_logger("Dumpatron")
        cmd = 'docker container stop $(docker container ls -a -q -f name=delegate_8)'
        cmd1 = 'docker kill $(docker container ls -a -q -f name=delegate_8)'

        # Bootstrap master
        for i, nodename in enumerate(self.groups['masternode']):
            self.execute_python(nodename, wrap_func(run_mn, i), async=True, profiling=self.PROFILE_TYPE)

        # Bootstrap witnesses
        for i, nodename in enumerate(self.groups['witness']):
            self.execute_python(nodename, wrap_func(run_witness, i), async=True, profiling=self.PROFILE_TYPE)

        # Bootstrap delegates
        for i, nodename in enumerate(self.groups['delegate']):
            # log.critical("print i -- {} node name -- {}".format(i, nodename))
            # if (i != 3):
            #     log.critical("executing i -- {} node name -- {}".format(i, nodename))
            self.execute_python(nodename, wrap_func(run_delegate, i), async=True, profiling=self.PROFILE_TYPE)

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
            self.execute_python('mgmt', wrap_func(dump_it, volume=vol), async=True, profiling=self.PROFILE_TYPE)


if __name__ == '__main__':
    unittest.main()
