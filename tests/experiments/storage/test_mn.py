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


def start_client(signing_key):
    import os
    import zmq, time
    from cilantro.logger.base import get_logger
    from tests.experiments.storage.test_master_store import MasterOps

    log = get_logger(os.getenv('MN'))

    mcount = len(TESTNET_MASTERNODES)
    log.info(mcount)
    log.info(signing_key)


    ctx = zmq.Context()
    socket = ctx.socket(socket_type=zmq.PAIR)
    url = "tcp://{}:10200".format(os.getenv('HOST_IP').split(',')[0])

    log.info("CLIENT CONNECTING TO {}".format(url))
    socket.connect(url)



    log.debug("waiting for msg...")
    msg = socket.recv_pyobj()

    socket.close()

def start_server():
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
    ctx = zmq.asyncio.Context()
    socket = ctx.socket(socket_type=zmq.PAIR)

    url = "tcp://{}:10200".format(os.getenv('HOST_IP'))
    log.info("SERVER BINDING TO {}".format(url))
    socket.bind(url)

    time.sleep(2)

    log.info("sending first msg")
    socket.send_pyobj("hello for the first time")


    socket.close()


class TestZMQPair(BaseNetworkTestCase):

    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro_mn.json')

    @vmnet_test
    def test_store(self):

        self.execute_python('mgmt', start_server)
        time.sleep(1)
        key = TESTNET_MASTERNODES[0]['sk']
     #   self.execute_python('mn', start_client())

        for node in self.groups['mn']:
        #    key = TESTNET_MASTERNODES[i]['sk']
            self.execute_python(node,wrap_func(start_client, signing_key = key))


        input("\n\nEnter any key to terminate")


if __name__ == '__main__':
    unittest.main()