from vmnet.test.base import BaseNetworkTestCase, vmnet_test
import unittest
import time

def run_node():
    import asyncio, os, zmq.auth
    from cilantro_ee.protocol.overlay.dht import DHT
    from cilantro_ee.logger import get_logger
    log = get_logger(__name__)

    signing_keys = {
        'node_1':'06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a',
        'node_2':'91f7021a9e8c65ca873747ae24de08e0a7acf58159a8aa6548910fe152dab3d8',
        'node_3':'f9489f880ef1a8b2ccdecfcad073e630ede1dd190c3b436421f665f767704c55',
        'node_4':'8ddaf072b9108444e189773e2ddcb4cbd2a76bbf3db448e55d0bfc131409a197',
        'node_5':'5664ec7306cc22e56820ae988b983bdc8ebec8246cdd771cfee9671299e98e3c',
        'node_6':'20b577e71e0c3bddd3ae78c0df8f7bb42b29b0c0ce9ca42a44e6afea2912d17b'
    }
    sk = signing_keys.get(os.getenv('HOSTNAME'))

    dht = DHT(mode='test', sk=sk, wipe_certs=True, block=False)


    dht.loop.run_forever()

class TestSecureConnection(BaseNetworkTestCase):
    testname = 'secure_connection'
    compose_file = 'cilantro_ee-nodes.yml'
    setuptime = 10

    @vmnet_test(run_webui=True)
    def test_setup_server_clients(self):
        self.execute_python('node_1', run_node, async=True)
        time.sleep(5)
        for node in ['node_{}'.format(n) for n in range(2,7)]:
            self.execute_python(node, run_node, async=True)
        input('Press any key to continue...')

if __name__ == '__main__':
    unittest.main()
