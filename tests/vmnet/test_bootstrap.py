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
    log = get_logger("MASTERNODE FACTORY")

    url = Constants.Testnet.Masternode.InternalUrl
    sk = Constants.Testnet.Masternode.Sk

    log.critical("\n\n\nMASTERNODE BOOTING WITH URL {} AND SK {}".format(url, sk))
    NodeFactory.run_masternode(url=url, signing_key=sk)


def run_witness(slot_num):
    from cilantro.logger import get_logger
    from cilantro import Constants
    from cilantro.nodes import NodeFactory
    log = get_logger("WITNESS FACTORY")

    w_info = Constants.Testnet.Witnesses[slot_num]

    log.critical("Building witness on slot {} with info {}".format(slot_num, w_info))
    NodeFactory.run_witness(url=w_info['url'], signing_key=w_info['sk'])


def run_delegate(slot_num):
    from cilantro.logger import get_logger
    from cilantro import Constants
    from cilantro.nodes import NodeFactory
    from cilantro.db import DB, DB_NAME

    log = get_logger("DELEGATE FACTORY")

    d_info = Constants.Testnet.Delegates[slot_num]

    # Set default database name for this instance
    with DB('{}_{}'.format(DB_NAME, slot_num), should_reset=True) as db:
        pass

    log.critical("Building witness on slot {} with info {}".format(slot_num, d_info))
    NodeFactory.run_delegate(url=d_info['url'], signing_key=d_info['sk'])


# def run_mgmt:

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


class TestBootstrap(BaseNetworkTestCase):
    testname = 'bootstrap'
    setuptime = 10
    compose_file = 'cilantro-bootstrap.yml'

    NUM_WITNESS = 2
    NUM_DELEGATES = 4

    def test_bootstrap(self):
    #     input("i wont die till u type something")
    #     return
        # Bootstrap MN
        self.execute_python('masternode', start_mysqld, async=True)
        time.sleep(1)

        self.execute_python('masternode', run_mn, async=True)

        # Bootstrap witnesses
        for i in range(self.NUM_WITNESS):
            self.execute_python('witness_{}'.format(i+1), start_mysqld, async=True)
            time.sleep(1)

            self.execute_python('witness_{}'.format(i+1), wrap_func(run_witness, i), async=True)

        # Bootstrap delegates
        for i in range(self.NUM_DELEGATES):
            self.execute_python('delegate_{}'.format(i+1), start_mysqld, async=True)
            time.sleep(1)

            self.execute_python('delegate_{}'.format(i+1), wrap_func(run_delegate, i), async=True)
            # time.sleep(1)

        input("\n\nEnter any key to terminate")

if __name__ == '__main__':
    unittest.main()
