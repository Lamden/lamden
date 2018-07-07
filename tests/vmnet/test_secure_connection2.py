from vmnet.test.base import BaseNetworkTestCase, vmnet_test
from vmnet.test.util import add_args
import unittest
import time

# def run_node():
#     import asyncio, os, zmq.auth
#     from cilantro.protocol.overlay.dht import DHT
#     from cilantro.logger import get_logger
#     log = get_logger(__name__)
#
#     signing_keys = {
#         'node_1':'06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a',
#         'node_2':'91f7021a9e8c65ca873747ae24de08e0a7acf58159a8aa6548910fe152dab3d8',
#         'node_3':'f9489f880ef1a8b2ccdecfcad073e630ede1dd190c3b436421f665f767704c55',
#         'node_4':'8ddaf072b9108444e189773e2ddcb4cbd2a76bbf3db448e55d0bfc131409a197',
#         'node_5':'5664ec7306cc22e56820ae988b983bdc8ebec8246cdd771cfee9671299e98e3c',
#         'node_6':'20b577e71e0c3bddd3ae78c0df8f7bb42b29b0c0ce9ca42a44e6afea2912d17b'
#     }
#     sk = signing_keys.get(os.getenv('HOSTNAME'))
#
#     dht = DHT(mode='test', sk=sk, wipe_certs=True, block=False)
#
#     dht.loop.run_forever()

def run_node(mode):
    import asyncio, os, zmq.auth, zmq, time
    from tests.overlay.utils import genkeys
    from cilantro.protocol.overlay.dht import DHT
    from cilantro.logger import get_logger
    log = get_logger(__name__)

    # DHT STUFF
    signing_keys = {
        'node_1':'06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a',
        'node_2':'91f7021a9e8c65ca873747ae24de08e0a7acf58159a8aa6548910fe152dab3d8',
        'node_3':'f9489f880ef1a8b2ccdecfcad073e630ede1dd190c3b436421f665f767704c55',
        'node_4':'8ddaf072b9108444e189773e2ddcb4cbd2a76bbf3db448e55d0bfc131409a197',
        'node_5':'5664ec7306cc22e56820ae988b983bdc8ebec8246cdd771cfee9671299e98e3c',
        'node_6':'20b577e71e0c3bddd3ae78c0df8f7bb42b29b0c0ce9ca42a44e6afea2912d17b'
    }
    sk = signing_keys.get(os.getenv('HOSTNAME'))
    dht = DHT(mode='test', sk=sk, wipe_certs=True, block=False)

    async def client(sock):
        log.critical('waiting for publish')
        while True:
            topic, msg = await sock.recv_multipart()
            log.critical('recieved::{}'.format(msg))

    async def server(sock):
        log.critical('waiting for connections')
        # msg = await sock.recv()
        # log.critical('connected')
        while True:
            log.critical('sending multi')
            sock.send_multipart([b'1', b'hello world'])
            # log.critical(sock)
            await asyncio.sleep(1)

    server_key = genkeys('06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a')['curve_key']
    client_key = genkeys('91f7021a9e8c65ca873747ae24de08e0a7acf58159a8aa6548910fe152dab3d8')['curve_key']
    sk = signing_keys.get(os.getenv('HOSTNAME'))
    ctx, auth = dht.network.ironhouse.secure_context(async=True)
    auth_port = 9001

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    if mode == 'pub':
        sock = ctx.socket(zmq.PUB)
        sec_sock = dht.network.ironhouse.secure_socket(sock)

        dht.network.ironhouse.create_from_public_key(client_key)
        dht.network.ironhouse.reconfigure_curve(auth)

        url = 'tcp://*:{}'.format(auth_port)
        log.info('Started pub server on {}'.format(url))
        sec_sock.bind(url)
        loop.run_until_complete(server(sec_sock))

    elif mode == 'sub':
        sock = ctx.socket(zmq.SUB)
        sock.setsockopt(zmq.SUBSCRIBE, b'1')
        sec_sock = dht.network.ironhouse.secure_socket(sock, curve_serverkey=server_key)
        log.critical(sec_sock)
        url = 'tcp://172.29.5.1:{}'.format(auth_port)
        log.info('Started listening as sub to {}'.format(url))
        sec_sock.connect(url)
        log.critical('ran connect without error')
        loop.run_until_complete(client(sec_sock))


run_pub = add_args(run_node, mode='pub')
run_sub = add_args(run_node, mode='sub')

class TestSecureConnection(BaseNetworkTestCase):
    testname = 'secure_connection'
    compose_file = 'cilantro-nodes.yml'
    setuptime = 10

    @vmnet_test(run_webui=True)
    def test_setup_server_clients(self):
        self.execute_python('node_1', run_pub, async=True)
        time.sleep(1)
        for node in ['node_{}'.format(n) for n in range(2,3)]:
            self.execute_python(node, run_sub, async=True)
        input('Press any key to continue...')

if __name__ == '__main__':
    unittest.main()
