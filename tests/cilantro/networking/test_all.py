from unittest import TestCase
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web

from cilantro.networking import Masternode, Delegate, Witness
from cilantro.serialization import JSONSerializer

from cilantro.networking.constants import MAX_REQUEST_LENGTH, TX_STATUS
from cilantro import config


m_ip = config['masternode'].get('ip')
m_int_port = config['masternode'].get('internal_port')
m_ext_port = config['masternode'].get('external_port')

d_ip = config['delegate'].get('ip')
d_port = config['delegate'].get('port')

w_ip = config['witness'].get('ip')