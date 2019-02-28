from vmnet.testcase import BaseNetworkTestCase
from cilantro_ee.utils.test.mp_test_case import vmnet_test
import unittest, time, random
import vmnet, cilantro_ee
from os.path import dirname, join
import time

cilantro_ee_path = dirname(dirname(cilantro_ee.__path__[0]))

def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper


def start_client():
    import zmq, time
    from cilantro_ee.logger.base import get_logger

    log = get_logger("ZMQ Client")
    ctx = zmq.Context()
    socket = ctx.socket(socket_type=zmq.PAIR)
    url = "tcp://{}:10200".format(os.getenv('NODE').split(',')[0])

    log.info("CLIENT CONNECTING TO {}".format(url))
    socket.connect(url)

    t = 0
    while t < 4:
        log.debug("waiting for msg...")
        msg = socket.recv_pyobj()
        log.info("got msg {}".format(msg))
        time.sleep(1)
        t += 1

    log.info('end!')

    socket.close()

def start_server():
    import os
    import asyncio
    import zmq.asyncio
    import time
    import uuid
    from cilantro_ee.logger.base import get_logger

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

    t = 0
    while t < 5:
        msg = uuid.uuid4().hex
        log.debug("sending msg {}".format(msg))
        socket.send_pyobj(msg)
        time.sleep(1)
        t += 1

    socket.close()

class TestZMQPair(BaseNetworkTestCase):

    config_file = join(dirname(cilantro_ee.__path__[0]), 'vmnet_configs', 'cilantro_ee-nodes.json')

    @vmnet_test
    def test_zmq_pair(self):
        self.execute_python('node_1', start_server)
        time.sleep(1)
        self.execute_python('node_2', start_client)
        input("\n\nEnter any key to terminate")


if __name__ == '__main__':
    unittest.main()
