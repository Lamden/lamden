from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('1-0-0.json')

from vmnet.testcase import BaseNetworkTestCase
import unittest, time, random, vmnet, cilantro
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test
from cilantro.utils.test.god import God
from cilantro.logger.base import get_logger
from cilantro.utils.test.god import God
from cilantro.logger import get_logger, overwrite_logger_level
import logging

LOG_LEVEL = 0


def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper


def run_mn():
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.nodes.factory import NodeFactory
    from cilantro.constants.testnet import TESTNET_MASTERNODES
    import os
    import logging

    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(21)
    # overwrite_logger_level(11)

    ip = os.getenv('HOST_IP')
    print("\n\n\ MN HAS IP {} \n\n".format(ip))
    sk = TESTNET_MASTERNODES[0]['sk']
    NodeFactory.run_masternode(ip=ip, signing_key=sk, reset_db=True)

    input("dont die pls")


def run_user():
    from cilantro.utils.test.god import God
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.protocol import wallet
    import logging

    # Fix masternode URL on God
    God.multi_master = False
    God.mn_urls = ['http://172.29.0.1:8080']

    log = get_logger("TestUser")
    # overwrite_logger_level(logging.WARNING)

    sk, vk = wallet.new()
    sk2, vk2 = wallet.new()

    # Request the nonce
    log.important("requesting nonce for vk: {}".format(vk))
    nonce = God.request_nonce(vk)
    log.important("got nonce return {}".format(nonce))
    assert 'success' in nonce, "'success' key not in nonce payload {}".format(nonce)
    assert 'nonce' in nonce, "'nonce' key not in nonce payload {}".format(nonce)

    log.notice("creating tx with nonce {}".format(nonce['nonce']))
    tx = God.create_currency_tx(sender=(sk, vk), receiver=(sk2, vk2), amount=10, nonce=nonce['nonce'])
    log.important("sending tx: {}".format(tx))
    r = God.send_tx(tx)

    log.important2("Got reply from sending tx: {} ... with json {}".format(r, r.json()))


class TestNonce(BaseNetworkTestCase):

    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-mn.json')
    PROFILE_TYPE = None

    @vmnet_test(run_webui=True)
    def test_dump(self):
        log = get_logger("test_dump")

        log.important3("Starting masternode")
        self.execute_python('mn', wrap_func(run_mn), async=True, profiling=self.PROFILE_TYPE)

        input("Press key to start mgmt")

        log.important3("Starting mgmt")
        self.execute_python('mgmt', wrap_func(run_user), async=True, profiling=self.PROFILE_TYPE)

        input("Press any key to exit...")


if __name__ == '__main__':
    unittest.main()
