import json
import logging
from time import sleep
import asyncio

from lamden.new_network import Network
from lamden.crypto.wallet import Wallet
import unittest
import sys
from datetime import datetime

from lamden.sockets.dealer import Dealer
from lamden.sockets.router import Router


class TestNewNetwork(unittest.TestCase):

    def await_async_process(self, process, args={}):
        tasks = asyncio.gather(
            process(**args)
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_start_stop_one_network(self):
        wallet = Wallet()
        boot_nodes = { wallet.verifying_key: ''}
        print(wallet.verifying_key)
        network1 = Network(wallet=wallet, socket_id='tcp://127.0.0.1:18080', max_peer_strikes=10, boot_nodes=boot_nodes)
        self.await_async_process(network1.start)
        self.async_sleep(1)
        self.assertTrue(network1.running)
        self.async_sleep(1)
        network1.stop()
        self.async_sleep(1)
        self.assertFalse(network1.running)

    def test_start_stop_two_networks(self):
        wallet1 = Wallet()
        wallet2 = Wallet()
        boot_nodes = {wallet1.verifying_key: '', wallet2.verifying_key: ''}
        network1 = Network(wallet=wallet1, socket_id='tcp://127.0.0.1:18080', max_peer_strikes=10, boot_nodes=boot_nodes)
        self.await_async_process(network1.start)
        self.async_sleep(0.5)
        self.assertTrue(network1.running)

        network2 = Network(wallet=wallet2, socket_id='tcp://127.0.0.1:18081', max_peer_strikes=10,
                           socket_ports={'router': 19001,'publisher': 19081},
                           boot_nodes=boot_nodes)
        self.await_async_process(network2.start)
        self.async_sleep(0.5)
        self.assertTrue(network2.running)

        network1.stop()
        network2.stop()
        self.async_sleep(1)
        self.assertFalse(network1.running)
        self.assertFalse(network2.running)

    def test_dealer_connect_to_network(self):
        wallet = Wallet()
        dealer_wallet = Wallet()
        boot_nodes = { wallet.verifying_key: '', dealer_wallet.verifying_key: ''}
        print(wallet.verifying_key)
        network1 = Network(wallet=wallet, socket_id='tcp://127.0.0.1:18080', max_peer_strikes=10, boot_nodes=boot_nodes)
        self.await_async_process(network1.start)
        self.async_sleep(1)
        self.assertTrue(network1.running)

        dealer = Dealer(_id=dealer_wallet.verifying_key, _address='tcp://127.0.0.1:19000',
                        server_vk=wallet.curve_vk, wallet=dealer_wallet, _callback=self.dealer_callback)

        dealer.start()

        self.async_sleep(1)
        self.assertEquals('pub_info', self.dealerCallbackMsg)

        test_str = 'test message'
        self.dealerCallbackMsg = ''
        dealer.send_msg(test_str)
        self.async_sleep(1)

        self.assertEquals('unhandled msg: ' + test_str, self.dealerCallbackMsg)

        self.async_sleep(2)

        network1.stop()
        dealer.stop()
        self.async_sleep(1)
        self.assertFalse(network1.running)

    def dealer_callback(self, msg):
        msg = str(msg, 'utf-8')
        print('dealer callback: ' + msg)
        try:
            msg_json = json.loads(msg)
            self.dealerCallbackMsg = msg_json['response']
        except:
            print('error decoding json')



    def test_connect(self):
        rootLogger = logging.getLogger()
        logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
        consoleHandler = logging.StreamHandler(sys.stdout)
        consoleHandler.setFormatter(logFormatter)
        rootLogger.addHandler(consoleHandler)
        print('starting test')
        wallet1 = Wallet()
        wallet2 = Wallet()
        boot_nodes = {wallet1.verifying_key: '', wallet2.verifying_key: ''}
        network1 = Network(wallet=wallet1, socket_id='tcp://127.0.0.1:18080', max_peer_strikes=10,
                           boot_nodes=boot_nodes)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ': ' + 'starting network1: ' + wallet1.verifying_key)
        self.await_async_process(network1.start)
        self.async_sleep(1)

        self.assertTrue(network1.running)

        network2 = Network(wallet=wallet2, socket_id='tcp://127.0.0.1:18081', max_peer_strikes=10,
                           socket_ports={'router': 19001, 'publisher': 19081},
                           boot_nodes=boot_nodes)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ': ' + 'starting network2: ' + wallet2.verifying_key)

        self.await_async_process(network2.start)
        self.async_sleep(1)
        self.assertTrue(network2.running)

        self.async_sleep(1)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ': ' + 'starting network1.connect')
        self.await_async_process(network1.connect,
                                 {'ip':'tcp://127.0.0.1', 'key': wallet2.verifying_key, 'ports': network1.socket_ports})
        self.async_sleep(3)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ': ' + 'checking network1.peer')
        # this is not working
        self.assertTrue(network1.peers[wallet2.verifying_key].running)

        network1.stop()
        network2.stop()
        self.async_sleep(1)
        self.assertFalse(network1.running)
        self.assertFalse(network2.running)


if __name__ == '__main__':
    unittest.main()