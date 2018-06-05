from vmnet.test.base import *
import unittest, time, random


import vmnet


def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper

def run_mn():
    from cilantro.logger import get_logger
    from cilantro import Constants
    from cilantro.nodes import NodeFactory
    from cilantro.db import DB, DB_NAME
    import os
    log = get_logger("MASTERNODE FACTORY")

    # with DB('{}_masternode'.format(DB_NAME), should_reset=True) as db:
    #     pass

    ip = os.getenv('HOST_IP') #Constants.Testnet.Masternodes[0]['ip']
    sk = Constants.Testnet.Masternodes[0]['sk']

    log.critical("\n\n\nMASTERNODE BOOTING WITH IP {} AND SK {}".format(ip, sk))
    NodeFactory.run_masternode(ip=ip, signing_key=sk)


def run_witness(slot_num):
    from cilantro.logger import get_logger
    from cilantro import Constants
    from cilantro.nodes import NodeFactory
    from cilantro.db import DB, DB_NAME
    import os

    log = get_logger("WITNESS FACTORY")

    # with DB('{}_witness_{}'.format(DB_NAME, slot_num), should_reset=True) as db:
    #     pass

    w_info = Constants.Testnet.Witnesses[slot_num]
    w_info['ip'] = os.getenv('HOST_IP')

    log.critical("Building witness on slot {} with info {}".format(slot_num, w_info))
    NodeFactory.run_witness(ip=w_info['ip'], signing_key=w_info['sk'])


def run_delegate(slot_num):
    from cilantro.logger import get_logger
    from cilantro import Constants
    from cilantro.nodes import NodeFactory
    from cilantro.db import DB, DB_NAME
    import os

    log = get_logger("DELEGATE FACTORY")

    d_info = Constants.Testnet.Delegates[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    # Set default database name for this instance
    # with DB('{}_delegate_{}'.format(DB_NAME, slot_num), should_reset=True) as db:
    #     pass

    log.critical("Building delegate on slot {} with info {}".format(slot_num, d_info))
    NodeFactory.run_delegate(ip=d_info['ip'], signing_key=d_info['sk'])


def pump_it(lamd, use_poisson):
    from cilantro.utils.test import God
    God.pump_it(rate=lamd, gen_func=God.random_std_tx, use_poisson=use_poisson)

def start_mysqld():
    import os
    os.system('mysqld \
   --skip-grant-tables \
   --skip-innodb \
   --collation-server latin1_bin \
   --default-storage-engine ROCKSDB \
   --default-tmp-storage-engine MyISAM \
   --binlog_format ROW \
   --user=mysql &')


class TestPump(BaseNetworkTestCase):

    EXPECTED_TRANSACTION_RATE = 0.1  # Avg transaction/second. lambda parameter in Poission distribution
    MODEL_AS_POISSON = False

    testname = 'pump_it'
    setuptime = 10
    compose_file = 'cilantro-bootstrap.yml'

    def test_bootstrap(self):
        # start mysql in all nodes
        for node_name in ['masternode'] + self.groups['witness'] + self.groups['delegate']:
            self.execute_python(node_name, start_mysqld, async=True)
        time.sleep(8)

        # Bootstrap master
        self.execute_python('masternode', run_mn, async=True)

        time.sleep(8)
        # Bootstrap witnesses
        for i, nodename in enumerate(self.groups['witness']):
            time.sleep(8)
            self.execute_python(nodename, wrap_func(run_witness, i), async=True)

        # Bootstrap delegates
        for i, nodename in enumerate(self.groups['delegate']):
            time.sleep(8)
            self.execute_python(nodename, wrap_func(run_delegate, i), async=True)

        # PUMP IT
        time.sleep(8)
        self.execute_python('mgmt', wrap_func(pump_it, self.EXPECTED_TRANSACTION_RATE, self.MODEL_AS_POISSON), async=True)

        input("\n\nEnter any key to terminate")

if __name__ == '__main__':
    unittest.main()
