from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('6-6-6.json')
import unittest
import vmnet, cilantro
import time
from configparser import SafeConfigParser
from os.path import dirname, join
from vmnet.testcase import BaseNetworkTestCase
from cilantro.utils.test.mp_test_case import vmnet_test
from cilantro.constants.testnet import TESTNET_MASTERNODES
from cilantro.storage.mongo import MDB
from cilantro.nodes.masternode.mn_api import StorageDriver
from cilantro.messages.block_data.block_data import BlockDataBuilder

cilantro_path = dirname(dirname(cilantro.__path__[0]))
cfg = SafeConfigParser()
cfg.read('{}/mn_db_conf.ini'.format(cilantro_path))

def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper


def start_mn(verifing_key):
    import os, zmq, time
    from cilantro.logger.base import get_logger
    from cilantro.nodes.masternode.master_store import MasterOps

    log = get_logger(os.getenv('MN'))
    log.info('Test 1 : init master')
    MasterOps.init_master(key = verifing_key)
    log.info('query db init state ')
    MDB.query_db()
    log.info('starting zmq setup')
    ctx = zmq.Context()
    socket = ctx.socket(socket_type=zmq.PAIR)
    url = "tcp://{}:10200".format(os.getenv('MGMT'))

    time.sleep(1)
    log.info("CLIENT CONNECTING TO {}".format(url))
    socket.connect(url)
    log.debug("waiting for msg...")
    msg = socket.recv_pyobj()
    log.debug('received: {}'.format(msg))

    log.info('Test 2 : writing 5 blocks')

    blk_id = 1
    while blk_id <= 5:
        log.debug("waiting for msg...")
        msg = socket.recv_pyobj()
        log.info("got msg {}".format(msg))

        block = BlockDataBuilder.create_block(blk_num = blk_id)
        success = StorageDriver.store_block(block, validate=False)
        log.info("wr status {}".format(success))
        time.sleep(1)
        blk_id += 1
    log.info('end! writes')

    log.info('print DB states')
    MDB.query_db()

    log.info('Test 3: verify lookup api')
    lasthash = StorageDriver.get_latest_block_hash()
    log.info('latest hash entry {}'.format(lasthash))

    log.info('Test 3.1 blk num from last blk hash')
    bk_num = MasterOps.get_blk_num_frm_blk_hash(blk_hash = lasthash)
    log.info ('result {}'.format(bk_num))

    socket.close()


def start_mgmt():
    import os, asyncio, zmq, time, zmq.asyncio
    from cilantro.logger.base import get_logger

    time.sleep(5)
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    log = get_logger("ZMQ Server")
    log.info("server host ip is {}".format(os.getenv('HOST_IP')))
    ctx = zmq.Context()
    socket = ctx.socket(socket_type=zmq.PAIR)

    url = "tcp://{}:10200".format(os.getenv('HOST_IP'))
    log.info("SERVER BINDING TO {}".format(url))
    socket.bind(url)

    time.sleep(2)

    log.info("sending first msg")

    socket.send_pyobj("hello for the first time")

    blk_num = 1
    while blk_num <= 5:
        msg = blk_num
        log.debug("sending msg {}".format(msg))
        socket.send_pyobj(msg)
        time.sleep(1)
        blk_num += 1

    socket.close()


class TestZMQPair(BaseNetworkTestCase):
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro_mn.json')

    @vmnet_test
    def test_store(self):

        self.execute_python('mgmt', start_mgmt)
        key = TESTNET_MASTERNODES[0]['vk']

        for node in self.groups['mn']:
           #key = TESTNET_MASTERNODES[i]['vk']
            print(node)

        self.execute_python(node,wrap_func(start_mn, verifing_key = key))

        input("\n\nEnter any key to terminate")

if __name__ == '__main__':
    unittest.main()
