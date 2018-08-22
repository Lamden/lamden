import unittest, cilantro, asyncio, zmq.asyncio, zmq
from unittest import TestCase
from cilantro.protocol.overlay.dht import DHT
from cilantro.protocol.overlay.network import Network
from os.path import exists, dirname
from threading import Timer
from cilantro.utils import ErrorWithArgs

from zmq.utils.z85 import decode, encode
from nacl.public import PrivateKey
from nacl.signing import SigningKey, VerifyKey
from nacl.bindings import crypto_sign_ed25519_sk_to_curve25519

def genkeys(sk_hex):
    sk = SigningKey(seed=bytes.fromhex(sk_hex))
    vk = sk.verify_key.encode().hex()
    public_key = VerifyKey(bytes.fromhex(vk)).to_curve25519_public_key()._public_key
    private_key = crypto_sign_ed25519_sk_to_curve25519(sk._signing_key)
    return {
        'sk': sk_hex,
        'vk': vk,
        'public_key': public_key.hex(),
        'private_key': encode(private_key),
        'curve_key': encode(public_key)
    }

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
