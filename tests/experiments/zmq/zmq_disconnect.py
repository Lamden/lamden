"""
    This experiment tests the behavior of the default disconnect.
"""

from cilantro.protocol.overlay.ironhouse import Ironhouse
from cilantro.constants.testnet import *
from cilantro.utils.test.mp_test_case import vmnet_test
import zmq, zmq.asyncio, time, asyncio, unittest, time, random, vmnet, cilantro, os, threading
from multiprocessing import Process
from vmnet.testcase import BaseNetworkTestCase

def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper

def start_client():
    import os, asyncio, zmq.asyncio, time
    from cilantro.logger import get_logger
    from cilantro.protocol.overlay.ironhouse import Ironhouse
    from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    log = get_logger("ZMQ Client")

    mn_vk, mn_public_key = Ironhouse.get_public_keys(TESTNET_MASTERNODES[0]['sk'])
    ih = Ironhouse(TESTNET_WITNESSES[0]['sk'])
    ih.setup_secure_server()
    ctx_sec, auth = Ironhouse.secure_context(True)
    socket_sec = Ironhouse.secure_socket(ctx_sec.socket(zmq.PAIR), ih.secret, ih.public_key, mn_public_key)

    MN_IP = os.getenv('NODE').split(',')[0]
    url_sec = "tcp://{}:10001".format(MN_IP)

    async def sec_listen():
        await asyncio.sleep(5)
        ih.reconfigure_curve(auth)
        log.critical("CLIENT CONNECTING TO {}".format(url_sec))
        socket_sec.connect(url_sec)
        log.info('Now listening (secure)')
        count = 0
        while True:
            msg = await socket_sec.recv()
            log.important('Received: {}'.format(msg))
            count += 1
            if count == 4:
                socket_sec.disconnect(url_sec)
                log.critical('DISCONNECTED!')
                await asyncio.sleep(5)
                log.critical("CLIENT RECONNECTING TO {}".format(url_sec))
                socket_sec.connect(url_sec)


    asyncio.ensure_future(sec_listen())
    loop.run_forever()

    socket_sec.close()

def start_server():
    import os, asyncio, zmq.asyncio, time
    from cilantro.logger import get_logger
    from cilantro.protocol.overlay.ironhouse import Ironhouse
    from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    log = get_logger("ZMQ Server")

    wn_vk, wn_public_key = Ironhouse.get_public_keys(TESTNET_WITNESSES[0]['sk'])
    ih = Ironhouse(TESTNET_MASTERNODES[0]['sk'])
    ih.setup_secure_server()
    ctx_sec, auth = Ironhouse.secure_context(True)
    socket_sec = Ironhouse.secure_socket(ctx_sec.socket(zmq.PAIR), ih.secret, ih.public_key)

    WN_IP = os.getenv('NODE').split(',')[1]
    url_sec = "tcp://*:10001"

    loop.run_until_complete(ih.authenticate(wn_public_key, WN_IP))

    ih.reconfigure_curve(auth)

    log.critical("SERVER BINDING TO {}".format(url_sec))
    socket_sec.bind(url_sec)

    async def send_msgs():
        await asyncio.sleep(5)
        count = 0
        while True:
            msg = "[{}]: sup".format(os.getenv('HOST_IP')) # b'sup'
            log.debug('<SECURE _{}_> {}'.format(count, msg).encode())
            socket_sec.send('<SECURE _{}_> {}'.format(count, msg).encode())
            count += 1
            await asyncio.sleep(0.5)

    asyncio.ensure_future(send_msgs())
    loop.run_forever()

    socket_sec.close()

class TestZMQDisconnect(BaseNetworkTestCase):

    config_file = '../../vmnet_configs/cilantro-nodes.json'

    @vmnet_test(run_webui=True)
    def test_zmq_disconnect(self):
        self.execute_python('node_1', start_server, async=True)
        self.execute_python('node_2', start_client, async=True)
        input("\n\nEnter any key to terminate")


if __name__ == '__main__':
    unittest.main()
