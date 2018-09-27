from vmnet.testcase import BaseNetworkTestCase
from cilantro.utils.test.mp_test_case import vmnet_test
from cilantro.constants.testnet import TESTNET_MASTERNODES
import unittest, time, random
import vmnet, cilantro
from os.path import dirname, join
import time

cilantro_path = dirname(dirname(cilantro.__path__[0]))

def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper


def start_mn(signing_key):
    import os
    import zmq, time
    from cilantro.logger.base import get_logger
    from tests.experiments.storage.test_master_store import MasterOps

    log = get_logger(os.getenv('MN'))

    count = MasterOps.get_master_set()
    log.info(count)

    mn_id = MasterOps.get_mn_id(sk = signing_key)
    rep_fact = MasterOps.get_rep_factor()


    # find master idx in pool
    pool_sz = MasterOps.rep_pool_sz(rep_fact,count)
    log.info(pool_sz)
    idx = MasterOps.mn_pool_idx(pool_sz,mn_id)
    log.info(idx)
    log.info(mn_id)


    ctx = zmq.Context()
    socket = ctx.socket(socket_type=zmq.PAIR)
    url = "tcp://{}:10200".format(os.getenv('MGMT'))

    time.sleep(1)
    log.info("CLIENT CONNECTING TO {}".format(url))
    socket.connect(url)


    log.debug("waiting for msg...")
    msg = socket.recv()
    log.debug("msg = {}".format(msg))

    blk_num = 1
    while blk_num <= 5:
        permit_wr = False
        log.debug("waiting for msg...")
        msg = socket.recv()
        log.info("got msg {}".format(msg))

        permit_wr = MasterOps.check_min_mn_wr(count, mn_id)
        if permit_wr == False:
            permit_wr = MasterOps.evaluate_wr(mn_idx=idx, blk_id=msg, pool_sz=pool_sz)
            log.info(permit_wr)

        log.info(permit_wr)
        log.info(msg)
        time.sleep(1)
        blk_num += 1


    log.info('end!')

    socket.close()

def start_mgmt():
    import os
    import asyncio
    import zmq.asyncio
    import time
    import uuid
    from cilantro.logger.base import get_logger

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

    socket.send(b"hello for the first time")

    blk_num = 1
    while blk_num <= 5:
        msg = blk_num
        log.debug("sending msg {}".format(msg))
        socket.send('{}'.format(msg).encode())
        time.sleep(1)
        blk_num += 1

    socket.close()


class TestZMQPair(BaseNetworkTestCase):

    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro_mn.json')

    @vmnet_test
    def test_store(self):

        self.execute_python('mgmt', start_mgmt)
        time.sleep(1)
        key = TESTNET_MASTERNODES[0]['sk']
     #   self.execute_python('mn', start_client())

        for node in self.groups['mn']:
        #    key = TESTNET_MASTERNODES[i]['sk']
            self.execute_python(node,wrap_func(start_mn, signing_key = key))


        input("\n\nEnter any key to terminate")


if __name__ == '__main__':
    unittest.main()