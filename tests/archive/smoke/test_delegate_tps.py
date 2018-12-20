from vmnet.testcase import BaseNetworkTestCase
import unittest, time, random


import vmnet


def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper

def run_mn():
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.constants.testnet import masternodes
    from cilantro.nodes import NodeFactory
    import os
    import logging
    from cilantro.logger.base import get_logger
    log = get_logger('M')

    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(21)

    ip = os.getenv('HOST_IP') #Constants.Testnet.Masternodes[0]['ip']
    sk = masternodes[0]['sk']
    NodeFactory.run_masternode(ip=ip, signing_key=sk, should_reset=True)


def run_witness(slot_num):
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.constants.testnet import witnesses
    from cilantro.nodes import NodeFactory
    import os
    import logging
    from cilantro.logger.base import get_logger
    log = get_logger('W')

    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(21)
    log.critical(slot_num)
    w_info = witnesses[slot_num]
    w_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_witness(ip=w_info['ip'], signing_key=w_info['sk'], should_reset=True)


def run_delegate(slot_num):
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.constants.testnet import delegates
    from cilantro.nodes import NodeFactory
    import os
    import logging
    from cilantro.logger.base import get_logger
    log = get_logger('D')

    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(21)
    log.critical(slot_num)
    d_info = delegates[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_delegate(ip=d_info['ip'], signing_key=d_info['sk'], should_reset=True)


def dump_it(volume):
    from cilantro.utils.test import God
    from cilantro.logger import get_logger, overwrite_logger_level
    import logging

    overwrite_logger_level(logging.WARNING)
    God._dump_it(volume=volume)


class TestPump(BaseNetworkTestCase):

    VOLUME = 2048  # Number of transactions to dump

    testname = 'delegate_tps'
    setuptime = 5
    compose_file = 'cilantro-delegate-flow.yml'

    @vmnet_test(run_webui=True)
    def test_bootstrap(self):

        # Bootstrap master
        self.execute_python('masternode', run_mn, async=True, profiling=True)

        # Bootstrap witnesses
        for i, nodename in enumerate(self.groups['witness'][:2]):
            self.execute_python(nodename, wrap_func(run_witness, i), async=True)

        # Bootstrap delegates
        for i, nodename in enumerate(self.groups['delegate'][:3]):
            self.execute_python(nodename, wrap_func(run_delegate, i), async=True, profiling=True)

        time.sleep(46)
        self.execute_python('mgmt', wrap_func(dump_it, self.VOLUME), async=True, profiling=True)

        input("Enter any key to terminate")

if __name__ == '__main__':
    unittest.main()
