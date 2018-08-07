from vmnet.test.base import *
import unittest, time, random
import vmnet, cilantro
from os.path import dirname
import time

cilantro_path = dirname(dirname(cilantro.__path__[0]))

def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper


def start_client():
    import zmq, time
    from cilantro.logger import get_logger

    log = get_logger("ZMQ Client")
    ctx = zmq.Context()
    socket = ctx.socket(socket_type=zmq.PAIR)
    url = "tcp://172.29.5.1:10200"

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

def start_server(xx=None):
    import os
    import asyncio
    import zmq.asyncio
    import time
    from cilantro.logger import get_logger

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    log = get_logger("ZMQ Server")
    log.critical(xx)
    log.info("server host ip is {}".format(os.getenv('HOST_IP')))
    assert os.getenv('HOST_IP') == '172.29.5.1', "what the heck host IP is not what we expected for node_1"
    ctx = zmq.asyncio.Context()
    socket = ctx.socket(socket_type=zmq.PAIR)

    url = "tcp://172.29.5.1:10200"
    log.info("SERVER BINDING TO {}".format(url))
    socket.bind(url)

    log.info("sending first msg")
    socket.send_pyobj("hello for the first time")

    t = 0
    while t < 5:
        msg = "sup" # b'sup'
        log.debug("sending msg {}".format(msg))
        socket.send_pyobj(msg)
        time.sleep(1)
        t += 1

    socket.close()

class TestZMQPair(BaseNetworkTestCase):
    testname = 'zmq_pair'
    setuptime = 6
    compose_file = '{}/cilantro/tests/vmnet/compose_files/cilantro-nodes.yml'.format(cilantro_path)
    local_path = cilantro_path
    docker_dir = '{}/cilantro/tests/vmnet/docker_dir'.format(cilantro_path)
    logdir = '{}/cilantro/logs'.format(cilantro_path)

    NUM_WITNESS = 2
    NUM_DELEGATES = 3

    @vmnet_test
    def test_zmq_pair(self):
        log = get_logger("TestZMQ")
        self.execute_python('node_2', start_client, async=True, profiling=True)
        self.execute_python('node_1', wrap_func(start_server, 1234), async=True, profiling=True)
        input("\n\nEnter any key to terminate")


if __name__ == '__main__':
    unittest.main()
