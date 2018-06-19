import unittest, cilantro, asyncio
from unittest import TestCase
from unittest.mock import patch
from cilantro.protocol.overlay.dht import *
from cilantro.protocol.overlay.network import *
from os.path import exists, dirname
from utils import genkeys
from threading import Timer
from cilantro.utils import ErrorWithArgs
from cilantro.protocol.overlay.utils import digest

class TestDHT(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.master = genkeys('06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a')
        self.witness = genkeys('91f7021a9e8c65ca873747ae24de08e0a7acf58159a8aa6548910fe152dab3d8')
        self.delegate = genkeys('8ddaf072b9108444e189773e2ddcb4cbd2a76bbf3db448e55d0bfc131409a197')

    def test_join_network_as_sole_master(self):
        def run(self):
            self.node.cleanup()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.node = DHT(sk=self.master['sk'],
                            mode='test',
                            port=3321,
                            keyname='master',
                            wipe_certs=True,
                            loop=self.loop,
                            max_wait=0.1,
                            block=False)

        self.assertEqual(self.node.network.ironhouse.vk, self.master['vk'])
        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_join_network_as_sole_non_master_node(self):
        def run(self):
            self.loop.call_soon_threadsafe(self.loop.stop)

        with self.assertRaises(ErrorWithArgs):
            self.node = DHT(sk=self.witness['sk'],
                                mode='test',
                                port=3321,
                                keyname='node',
                                wipe_certs=True,
                                loop=self.loop,
                                max_wait=0.1,
                                block=False,
                                retry_discovery=1)


        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def tearDown(self):
        self.loop.close()

if __name__ == '__main__':
    unittest.main()
