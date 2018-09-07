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

def client(i):
    import zmq, asyncio, os, zmq.asyncio
    from cilantro.protocol.overlay.ironhouse import Ironhouse
    from cilantro.logger.base import get_logger
    log = get_logger('sub')
    async def connect(ih_ins):
        await asyncio.sleep(4)
        # Dummy keys shared by masternodes
        svr_vk, svr_public, svr_secret = Ironhouse.generate_certificates('a2ac4e2dcdd342fcadf79db4486948df3078329b6aa543f1952dab2ac36cfafe')

        ctx, auth = Ironhouse.secure_context(True)
        ih_ins.reconfigure_curve(auth, 'pubsub')
        sock = Ironhouse.secure_socket(ctx.socket(zmq.SUB),
            ih_ins.secret, ih_ins.public_key, svr_public)
        sock.setsockopt(zmq.SUBSCRIBE, b'topic')
        nodes = os.getenv('NODE').split(',')
        log.critical('connecting to {}'.format("tcp://{}:{}".format(nodes[0], 9999)))
        sock.connect("tcp://{}:{}".format(nodes[0], 9999))
        log.critical('connecting to {}'.format("tcp://{}:{}".format(nodes[1], 9999)))
        sock.connect("tcp://{}:{}".format(nodes[1], 9999))

        while True:
            topic, msg = await sock.recv_multipart()
            log.critical('{} Received: {}'.format(os.getenv('HOST_IP'), msg))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ih = Ironhouse(sk=TESTNET_DELEGATES[i]['sk'])
    ih.setup_secure_server()
    asyncio.ensure_future(connect(ih))
    loop.run_forever()

def server(i):
    import zmq, asyncio, os, zmq.asyncio
    from cilantro.protocol.overlay.ironhouse import Ironhouse
    from cilantro.logger.base import get_logger
    log = get_logger('pub')
    async def bind(ih_ins):
        # Dummy keys shared by masternodes
        svr_vk, svr_public, svr_secret = Ironhouse.generate_certificates('a2ac4e2dcdd342fcadf79db4486948df3078329b6aa543f1952dab2ac36cfafe')

        ctx, auth = Ironhouse.secure_context(True)
        sock = Ironhouse.secure_socket(ctx.socket(zmq.PUB),
            svr_secret, svr_public)
        log.critical('binding to {}'.format("tcp://*:{}".format(9999)))
        sock.zap_domain = b'pubsub'
        sock.bind("tcp://*:{}".format(9999))
        await asyncio.sleep(3)
        ih_ins.reconfigure_curve(auth, 'pubsub')
        while True:
            log.critical('{} sending stuff!'.format(os.getenv('HOST_IP')))
            sock.send_multipart([b'topic', os.getenv('HOST_IP').encode()])
            await asyncio.sleep(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    cli1_vk, cli1_public, _ = Ironhouse.generate_certificates(TESTNET_DELEGATES[0]['sk'])
    cli2_vk, cli2_public, _ = Ironhouse.generate_certificates(TESTNET_DELEGATES[1]['sk'])
    ih = Ironhouse(sk=TESTNET_MASTERNODES[i]['sk'], wipe_certs=True)
    nodes = os.getenv('NODE').split(',')
    ih.setup_secure_server()
    asyncio.ensure_future(ih.authenticate(cli1_public, nodes[2], domain='pubsub'))
    asyncio.ensure_future(ih.authenticate(cli2_public, nodes[3], domain='pubsub'))
    asyncio.ensure_future(bind(ih))
    loop.run_forever()

class TestZMQMultSub(BaseNetworkTestCase):
    config_file = '../../vmnet_configs/cilantro-nodes.json'
    @vmnet_test(run_webui=True)
    def test_vklookup(self):

        self.execute_python('node_1', wrap_func(server, 0))
        self.execute_python('node_2', wrap_func(server, 1))
        self.execute_python('node_3', wrap_func(client, 0))
        self.execute_python('node_4', wrap_func(client, 1))

        input("Enter any key to terminate")


if __name__ == '__main__':
    unittest.main()
