"""
    Test to see if different ZMQ contexts can share the same loop.
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

    ctx = zmq.asyncio.Context()
    socket = ctx.socket(socket_type=zmq.PAIR)

    MN_IP = os.getenv('NODE').split(',')[0]
    url = "tcp://{}:10000".format(MN_IP)
    url_sec = "tcp://{}:10001".format(MN_IP)

    async def listen():
        log.critical("CLIENT CONNECTING TO {}".format(url))
        socket.connect(url)
        log.info('Now listening (not secure)')
        while True:
            msg = await socket.recv_pyobj()
            log.important('Received: {}'.format(msg))

    async def sec_listen():
        await asyncio.sleep(5)
        ih.reconfigure_curve(auth)
        log.critical("CLIENT CONNECTING TO {}".format(url_sec))
        socket_sec.connect(url_sec)
        log.info('Now listening (secure)')
        while True:
            msg = await socket_sec.recv()
            log.important('Received: {}'.format(msg))

    asyncio.ensure_future(listen())
    asyncio.ensure_future(sec_listen())
    loop.run_forever()

    socket.close()
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

    ctx = zmq.asyncio.Context()
    socket = ctx.socket(socket_type=zmq.PAIR)

    WN_IP = os.getenv('NODE').split(',')[1]
    url = "tcp://*:10000"
    url_sec = "tcp://*:10001"
    log.info("SERVER BINDING TO {}".format(url))
    socket.bind(url)

    loop.run_until_complete(ih.authenticate(wn_public_key, WN_IP))

    ih.reconfigure_curve(auth)

    log.critical("SERVER BINDING TO {}".format(url_sec))
    socket_sec.bind(url_sec)

    async def send_msgs():
        await asyncio.sleep(5)
        while True:
            msg = "[{}]: sup".format(os.getenv('HOST_IP')) # b'sup'
            log.debug('sending <NOT_SECURE> {}'.format(msg))
            socket.send_pyobj('<NOT_SECURE> {}'.format(msg))
            log.debug('sending <SECURE> {}'.format(msg))
            socket_sec.send('<SECURE> {}'.format(msg).encode())
            await asyncio.sleep(1)

    asyncio.ensure_future(send_msgs())
    loop.run_forever()

    socket.close()
    socket_sec.close()

class TestZMQContext(BaseNetworkTestCase):

    config_file = '../../vmnet_configs/cilantro-nodes.json'

    @vmnet_test(run_webui=True)
    def test_zmq_context(self):
        self.execute_python('node_1', start_server, async=True)
        self.execute_python('node_2', start_client, async=True)
        input("\n\nEnter any key to terminate")


if __name__ == '__main__':
    unittest.main()
