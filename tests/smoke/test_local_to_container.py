from vmnet.testcase import BaseNetworkTestCase
import unittest, time, random, os, zmq
from cilantro.utils.test.mp_test_case import vmnet_test
import vmnet
from cilantro.logger import get_logger
log = get_logger(__name__)

def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper

def run_container():
    from cilantro.logger import get_logger
    from cilantro.protocol.overlay.interface import OverlayServer, OverlayClient
    from multiprocessing import Process
    import os, time, zmq

    log = get_logger('container')

    ctx = zmq.Context()
    sock = ctx.socket(zmq.PAIR)
    url = 'tcp://{}:10200'.format(os.getenv('HOST_IP'))
    log.critical('Container: {}'.format(url))
    sock.bind(url)

    while True:
        log.critical('Sending.')
        sock.send(b'slick')
        time.sleep(1)

class TestOverlayInterface(BaseNetworkTestCase):
    config_file = '../../vmnet_configs/cilantro-nodes.json'

    @vmnet_test(run_webui=True)
    def test_vklookup(self):

        # Bootstrap master
        self.execute_python('node_1', run_container)

        ctx = zmq.Context()
        sock = ctx.socket(zmq.PAIR)
        url = 'tcp://{}'.format(self.ports['node_1']['10200'])
        log.critical('Local: {}'.format(url))
        sock.connect(url)
        while True:
            msg = sock.recv()
            log.important('Received: {}'.format(msg))

        input("Enter any key to terminate")

if __name__ == '__main__':
    unittest.main()
