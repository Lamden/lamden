from cilantro_ee.utils.test.testnet_config import set_testnet_config
set_testnet_config('6-6-6.json')
import unittest
import cilantro_ee
from configparser import SafeConfigParser
from os.path import dirname, join
from vmnet.testcase import BaseNetworkTestCase
from cilantro_ee.utils.test.mp_test_case import vmnet_test
from cilantro_ee.constants.testnet import TESTNET_MASTERNODES
from cilantro_ee.storage.mongo import MDB
from cilantro_ee.storage.mn_api import StorageDriver

cilantro_ee_path = dirname(dirname(cilantro_ee.__path__[0]))
cfg = SafeConfigParser()
cfg.read('{}/mn_db_conf.ini'.format(cilantro_ee_path))

def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper


def start_mn(verifing_key):
    from cilantro_ee.utils.sketch import sketch
    sketch()

    import os, zmq, time
    from cilantro_ee.logger.base import get_logger, overwrite_logger_level
    from cilantro_ee.nodes.masternode.master_store import MasterOps
    from cilantro_ee.messages.block_data.sub_block import SubBlockBuilder
    from cilantro_ee.storage.state import StateDriver

    overwrite_logger_level(12)

    MN_SK = TESTNET_MASTERNODES[0]['sk'] if len(TESTNET_MASTERNODES) > 0 else 'A' * 64
    log = get_logger(os.getenv('MN'))
    log.info('Test 1 : init master')
    MasterOps.init_master(key = verifing_key)
    log.info('result query db init state ')
    MDB.query_db()
    log.info('starting zmq setup')
    ctx = zmq.Context()
    socket = ctx.socket(socket_type=zmq.PAIR)
    url = "tcp://{}:10200".format(os.getenv('MGMT'))

    time.sleep(1)
    log.info("CLIENT CONNECTING TO {}".format(url))
    socket.connect(url)
    log.info("waiting for msg...")
    msg = socket.recv_pyobj()
    log.debug('received: {}'.format(msg))

    log.info('Test 2 : writing 5 blocks')

    blk_id = 1
    while blk_id <= 2:
        log.debug("waiting for msg...")
        msg = socket.recv_pyobj()
        log.info("got msg {}".format(msg))

        last_blk_hash = bool(StorageDriver.get_latest_block_hash())
        print("WHY-WHY-WHY")
        print(last_blk_hash)
        print(StorageDriver.get_latest_block_hash())
        print("**********************")


        bhash, bnum = StateDriver.get_latest_block_info()
        log.debugv("DAVIS STATE DRIVER - {} hash - {}".format(bnum, bhash))

        sub_blocks = [SubBlockBuilder.create(idx=i) for i in range(2)]
        block = StorageDriver.store_block(sub_blocks)
        StateDriver.update_with_block(block = block)

        bhash, bnum = StateDriver.get_latest_block_info()
        log.debugv("state binfo num - {} hash - {}".format(bnum, bhash))
        time.sleep(1)
        blk_id += 1
    log.info('end! writes')

    log.info('print DB states')
    MDB.query_db()

    log.info('Test 3: verify lookup api')
    lasthash = StorageDriver.get_latest_block_hash()
    log.info('latest hash entry -> {}'.format(lasthash))

    log.info('Test 3.1 blk num from last blk hash')
    bk_num = MasterOps.get_blk_num_frm_blk_hash(blk_hash = lasthash)
    log.info('blk num from lookup {}'.format(bk_num))

    log.info('Test 3.2 Get list of 3 blocks')
    blk_delta = MasterOps.get_blk_idx(n_blks = 3)
    log.info('print blk_delta -> {}'.format(blk_delta))

    log.info('end test')
    socket.close()


def start_mgmt():
    import os, asyncio, time, zmq.asyncio
    from cilantro_ee.logger.base import get_logger

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
    while blk_num <= 2:
        msg = blk_num
        log.debug("sending msg {}".format(msg))
        socket.send_pyobj(msg)
        time.sleep(1)
        blk_num += 1

    socket.close()


class TestZMQPair(BaseNetworkTestCase):
    config_file = join(dirname(cilantro_ee.__path__[0]), 'vmnet_configs', 'cilantro_ee-mn.json')

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
