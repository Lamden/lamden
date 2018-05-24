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
    import os
    log = get_logger("MASTERNODE FACTORY")

    ip = os.getenv('HOST_IP') #Constants.Testnet.Masternodes[0]['ip']
÷
    log.critical("\n\n\nMASTERNODE BOOTING WITH IP {} AND SK {}".format(ip, sk))
    NodeFactory.run_masternode(ip=ip, signing_key=sk)


def run_witness(slot_num):
    from cilantro.logger import get_logger
    from cilantro import Constants
    from cilantro.nodes import NodeFactory
    import os
    log = get_logger("WITNESS FACTORY")

    w_info = Constants.Testnet.Witnesses[slot_num]
    w_info['ip'] = os.getenv('HOST_IP')

    log.critical("Building witness on slot {} with info {}".format(slot_num, w_info))
    NodeFactory.run_witness(ip=w_info['ip'], signing_key=w_info['sk'])


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
    testname = 'mn_witness'
    setuptime = 10
    compose_file = 'cilantro-bootstrap.yml'

    NUM_WITNESS = 2
    NUM_DELEGATES = 4

    def test_bootstrap(self):
        # start mysql in all nodes
        for node_name in ['masternode'] + ['witness_{}'.format(i+1+1) for i in range(self.NUM_WITNESS)]:
            self.execute_python(node_name, start_mysqld, async=True)
        time.sleep(3)

        # Bootstrap master
        self.execute_python('masternode', run_mn, async=True)

        # Bootstrap witnesses
        for i in range(self.NUM_WITNESS):
            self.execute_python('witness_{}'.format(i+1+1), wrap_func(run_witness, i), async=True)

        input("\n\nEnter any key to terminate")

if __name__ == '__main__':
    unittest.main()
