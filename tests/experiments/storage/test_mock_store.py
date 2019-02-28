import unittest, time, cilantro_ee
from vmnet.testcase import BaseNetworkTestCase
from cilantro_ee.utils.test.mp_test_case import vmnet_test
from cilantro_ee.constants.testnet import TESTNET_MASTERNODES
from os.path import dirname, join
from cilantro_ee.storage.vkbook import VKBook

cilantro_ee_path = dirname(dirname(cilantro_ee.__path__[0]))

def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper

def start_mn(verifing_key):
    import os, zmq, time, asyncio
    from cilantro_ee.logger.base import get_logger
    from tests.experiments.storage.test_master_store import MasterOps

    log = get_logger(os.getenv('MN'))

    count = MasterOps.get_master_set()
    mn_id = MasterOps.get_mn_id(vk = verifing_key)
    rep_fact = MasterOps.get_rep_factor()

    # find master idx in pool
    pool_sz = MasterOps.rep_pool_sz(rep_fact,count)
    log.info("pool size {}".format(pool_sz))
    idx = MasterOps.mn_pool_idx(pool_sz,mn_id)

    ctx = zmq.Context()
    socket = ctx.socket(socket_type=zmq.SUB)
    url = "tcp://{}:10200".format(os.getenv('HOST_NAME'))

    time.sleep(1)
    log.info("CLIENT CONNECTING TO {}".format(url))
    socket.connect(url)


    log.debug("waiting for msg...")
    msg = socket.recv_pyobj()
    log.info("msg {}".format(msg))
    log.info("total masters {}".format(count))
    log.info("master index {}".format(idx))
    log.info("master id {}".format(mn_id))

    blk_num = 1
    while blk_num <= 5:
        log.debug("waiting for msg...")
        msg = socket.recv_pyobj()
        log.info("got msg {}".format(msg))

        # check for every time if we have
        permit_wr = MasterOps.check_min_mn_wr(rep_fact=rep_fact,mn_set=count,id=mn_id)
        log.info("1")
        log.info(permit_wr)

        if permit_wr == False:
            permit_wr = MasterOps.evaluate_wr(mn_idx=idx, blk_id=msg, pool_sz=pool_sz)
            log.info("2")
            log.info(permit_wr)

        if permit_wr == True:
            # write to store
            log.info("committing msg {}".format(msg))
            log.info("3")
            permit_wr = False

        log.info("4")
        log.info(permit_wr)
        time.sleep(1)
        blk_num += 1


    log.info('end!')
    socket.close()

def start_mgmt():
    import asyncio, zmq, zmq.asyncio, os, time
    from cilantro_ee.logger.base import get_logger

    log = get_logger('mgmt')

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    log.info("server host ip is {}".format(os.getenv('HOST_IP')))
    ctx = zmq.Context()
    socket = ctx.socket(socket_type=zmq.PUB)

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


class TestMockStore(BaseNetworkTestCase):

    config_file = join(dirname(cilantro_ee.__path__[0]), 'vmnet_configs', 'cilantro_ee-multi-master.json')

    @vmnet_test
    def test_store(self):
        self. execute_python('mgmt', start_mgmt)
        time.sleep(1)

        masters = VKBook.get_masternodes()
        print(masters)

        i = len(masters)
        for node in self.groups['mn']:
            if i <= 0:
                break
            key = TESTNET_MASTERNODES[len(masters)-i]['vk']
            self.execute_python(node, wrap_func(start_mn, verifing_key=key))
            i-=1
            print(key)
            print(node)


        input("\n\nEnter any key to terminate")

if __name__ == '__main__':
    unittest.main()
