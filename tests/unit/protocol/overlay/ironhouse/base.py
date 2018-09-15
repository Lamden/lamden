import unittest
from unittest import TestCase
import zmq, zmq.asyncio, asyncio
from zmq.auth.thread import ThreadAuthenticator
from zmq.auth.asyncio import AsyncioAuthenticator
from cilantro.protocol.overlay.ironhouse import Ironhouse
from zmq.utils.z85 import decode, encode
from os import listdir, makedirs
from os.path import exists
from threading import Timer
import asyncio, shutil
from cilantro.utils.test.overlay import *
from cilantro.constants.testnet import *

def auth_validate(vk):
    print('Test: Received on validation: {}'.format(vk))
    return True

class TestIronhouseBase(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        keys = genkeys(TESTNET_MASTERNODES[0]['sk'])
        self.sk = TESTNET_MASTERNODES[0]['sk']
        self.vk = TESTNET_MASTERNODES[0]['vk']
        self.private_key = keys['secret_key']
        self.public_key = keys['public_key']
        self.curve_public_key = keys['curve_key']
        self.keyname = decode(self.curve_public_key).hex()
        self.ironhouse = Ironhouse(self.sk, auth_validate=auth_validate)
        self.secret = self.ironhouse.secret
