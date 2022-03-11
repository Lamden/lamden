import json
import logging
import traceback
from time import sleep
import asyncio

from lamden.new_network import Network
from lamden.crypto.wallet import Wallet
import unittest
import sys
from datetime import datetime

from lamden.sockets.dealer import Dealer
from lamden.sockets.request import Request
from lamden.sockets.router import Router


class TestNewNetwork(unittest.TestCase):
    def setUp(self):
        self.router_callback_msg = None

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

    def request_callback(self, success: bool, msg):
        self.request_successful = success
        if(success):
            msg = str(msg, 'utf-8')
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ': ' + 'request callback: ' + msg)
            try:
                msg_json = json.loads(msg)
                self.dealerCallbackMsg = msg_json['action']
            except:
                print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ': ' +
                      'request call back error decoding json')
        else:
            print('request failed: ' + msg)

    def dealer_callback(self, msg):
        msg = str(msg, 'utf-8')
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ': ' + 'dealer callback: ' + msg)
        try:
            msg_json = json.loads(msg)
            self.dealerCallbackMsg = msg_json['action']
        except:
            print('error decoding json')

    def router_callback(self, router: Router, identity, msg):
        msgStr = str(msg, 'utf-8')
        print(f'router callback, ident: {str(identity)}, msg: {msgStr}')
        self.router_callback_msg = msgStr
        msg = b'success'
        router.send_msg(identity, msg)

    def test_request_to_router(self):
        request_wallet = Wallet()
        router_wallet = Wallet()

        request = Request(_id=request_wallet.verifying_key, _address='tcp://127.0.0.1:19000',
                          server_vk=router_wallet.curve_vk, wallet=request_wallet)

        router = Router(router_wallet=router_wallet, get_all_peers=lambda: [request_wallet.verifying_key],
                        callback=self.router_callback)
        router.address = 'tcp://127.0.0.1:19000'

        router.start()
        # Wait for router to start
        self.async_sleep(0.5)

        msg = '{"action": "test"}'
        # The below call is blocking and will wait until it is complete
        result = request.send_msg_await(msg=msg, time_out=500, retries=3)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ': ' + 'after sending test message')
        self.async_sleep(2)
        router.stop()

        self.assertEqual(msg, self.router_callback_msg)
        self.assertEqual(True, result.success)
        self.assertEqual(b'success', result.response)

    def test_request_failed(self):
        dealer_wallet = Wallet()
        router_wallet = Wallet()

        request = Request(_id=dealer_wallet.verifying_key, _address='tcp://127.0.0.1:19000',
                          server_vk=router_wallet.curve_vk, wallet=dealer_wallet)

        self.async_sleep(0.5)
        self.request_successful = None
        msg = '{"action": "test"}'
        # The below call is blocking and will wait until it is complete
        result = request.send_msg_await(msg=msg, time_out=100, retries=1)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ': ' + 'after sending test message')
        # self.async_sleep(5)
        request.stop()

        self.assertEqual(False, result.success)
        self.assertEqual('Request Socket Error: Failed to receive response after 1 attempts each waiting 100', result.response)
if __name__ == '__main__':
    unittest.main()