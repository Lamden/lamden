from vmnet.test.base import BaseNetworkTestCase
import unittest
import time

def run_node():
    import asyncio, os, zmq.auth
    from cilantro.protocol.overlay.dht import DHT
    from cilantro.logger import get_logger
    log = get_logger(__name__)

    # node_1_vk = '4aeba121f535ac9cc2b2c6a6629988308de5fca9aadc57b2023e19e3d83f4f88'

    def auth_payload():
        payload = '4aeba121f535ac9cc2b2c6a6629988308de5fca9aadc57b2023e19e3d83f4f88'
        log.debug('Generating auth_payload of "{}"'.format(payload))
        # TODO in cilantro integrated tests, call VKBook.get_masternodes()
        return payload

    def auth_callback(payload):
        correct_payload = b'4aeba121f535ac9cc2b2c6a6629988308de5fca9aadc57b2023e19e3d83f4f88'
        log.debug('masternode_vk = {}'.format(payload))
        return correct_payload == payload

    # For DEBUG test only
    private_keys = {
        'node_1':'133852f51ae13329e9776027529f3d2ef64459d65efca172fbc4a5487896cae1',
        'node_2':'a8be57386aa395206536c50f4f3e7777733afc6c956f372f19e22e30ca5ec5db',
        'node_3':'1479ee002156b36b48609166f9af1491e0e6eac583e4270e000f804bb8f0fec7',
        'node_4':'e8f49c14a8320f93f00f0a38679a0f467e6bf2e12f05db6e2f7fe46d878f4e1a',
        'node_5':'bb54502754ad80119632236b77a72577d725e9cd2d863d0ac9bc38568bdc9f89',
        'node_6':'c4c56cf9a0b5ac73905a36826cce1e1c2bbcafb8576a72194c8808d82bb1ec13',
        'node_7':'18e6cd97fb67f5331b9fea94ae005adef5521a79a79c5f33a62269e5ad01d3dc',
        'node_8':'8d6ef7188a302898387d5e9e14fe8154abcad4a9851ebd5d9100f6a6bdfe5a55',
    }
    private_key = private_keys.get(os.getenv('HOSTNAME'))

    dht = DHT(mode='test', auth_payload=auth_payload, auth_callback=auth_callback, private_key=private_key, wipe_certs=True)
    dht.loop.run_forever()

class TestSecureConnection(BaseNetworkTestCase):
    testname = 'secure_connection'
    compose_file = 'cilantro-nodes.yml'
    setuptime = 10
    def test_setup_server_clients(self):
        for node in ['node_{}'.format(n) for n in range(1,8)]:
            self.execute_python(node, run_node, async=True)
        input('Press any key to continue...')

if __name__ == '__main__':
    unittest.main()
