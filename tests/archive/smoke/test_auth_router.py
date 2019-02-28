from vmnet.testcase import BaseTestCase
from vmnet.comm import file_listener
import unittest, time, random, vmnet, cilantro_ee
from os.path import join, dirname
from cilantro_ee.utils.test.mp_test_case import wrap_func
from cilantro_ee.logger.base import get_logger
from cilantro_ee.constants.testnet import *


def nodefn(sk, ip_vk_dict, expected_ip, use_auth):
    from zmq.auth.asyncio import AsyncioAuthenticator
    from cilantro_ee.protocol.overlay.auth import Auth
    from cilantro_ee.logger.base import get_logger
    from vmnet.comm import send_to_file
    import asyncio, json, os, zmq.asyncio, zmq, traceback, time
    assert os.getenv('HOST_IP') == expected_ip, "we fukt up"

    class RouterAuth:
        PORT = 6967
        def __init__(self, sk, use_auth=True, loop=None, ctx=None):
            assert loop, "must pass in loop"
            assert ctx, "must pass in context"
            self.sk = sk
            self.use_auth = use_auth
            self.log = get_logger('RouterAuth')
            self.loop = loop or asyncio.get_event_loop()
            self.ctx = ctx or zmq.asyncio.Context()
            self.ip = os.getenv('HOST_IP')

            if use_auth:
                self.log.notice("Configuring authentication")
                Auth.setup(sk)
                self.auth = AsyncioAuthenticator(context=self.ctx, loop=self.loop)
                self.auth.configure_curve(domain='*', location=zmq.auth.CURVE_ALLOW_ANY)
                self.auth.start()
                time.sleep(3)


            self.dealers = {}
            self.router = self.ctx.socket(zmq.ROUTER)
            self.router.setsockopt(zmq.IDENTITY, self.ip.encode())
            self.router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY

            self.reply_ids = set()

            if use_auth:
                self.router.curve_secretkey = Auth.private_key
                self.router.curve_publickey = Auth.public_key
                self.router.curve_server = True

            url = 'tcp://{}:{}'.format(os.getenv('HOST_IP'), self.PORT)
            # url = 'tcp://*:{}'.format(self.PORT)
            self.log.socket("BINDING to url {}".format(url))
            self.router.bind(url)

        async def listen(self):
            while True:
                try:
                    self.log.spam("router waiting for msg...")
                    ip, msg = await self.router.recv_multipart()
                    self.log.notice('Received msg {} from ip {}'.format(msg, ip))
                    reply_msg = "Thanks for the msg <{}>, this is {}'s reply".format(msg.decode(), self.ip)
                    self.log.important2("Replying to ID {} with msg {}".format(ip, reply_msg))
                    self.router.send_multipart([ip, self.ip.encode(), reply_msg.encode()])
                except Exception as e:
                    self.log.fatal(traceback.format_exc())

        async def send_request(self, ip, vk=None):
            if ip in self.dealers:
                self.log.info("Request already pending for ip {}!".format(ip))
                return

            self.log.notice("Sending REQUEST to ip {} with vk {}".format(ip, vk))

            self.dealers[ip] = self.ctx.socket(zmq.DEALER)
            self.dealers[ip].setsockopt(zmq.IDENTITY, self.ip.encode())

            if self.use_auth:
                assert vk, "Must pass in VK to use auth"
                self.dealers[ip].curve_secretkey = Auth.private_key
                self.dealers[ip].curve_publickey = Auth.public_key
                self.dealers[ip].curve_serverkey = Auth.vk2pk(vk)

            req_msg = 'req from {}'.format(self.ip).encode()
            url = 'tcp://{}:{}'.format(ip, self.PORT)
            self.log.socket("CONNECTING to url {}".format(url))
            self.dealers[ip].connect(url)

            try:
                self.dealers[ip].send_multipart([req_msg])
                self.log.important("Dealer socket send request to ip {} and waiting for reply...".format(ip))
                # time.sleep(0.1)  # for debug (should not need this)
                ip, msg = await asyncio.wait_for(self.dealers[ip].recv_multipart(), 5)
                ip = ip.decode()
                self.log.important3('Received reply: {} from {}'.format(msg, ip))
                self.reply_ids.add(ip)
                self.log.info("Closing dealer socket on ip {}".format(ip))
                self.dealers[ip].close()
                del self.dealers[ip]

            except Exception as e:
                self.log.fatal(traceback.format_exc())

    async def send_request(n):
        await asyncio.sleep(5)
        await asyncio.gather(*[
            n.send_request(ip, node_info[0]) \
                for ip, node_info in ip_vk_dict.items() \
                if os.getenv('HOST_IP') != ip
        ])

    async def check_succ(n):
        succ = False
        for _ in range(15):
            await asyncio.sleep(1)
            if len(n.reply_ids) == len(ip_vk_dict) - 1:
                log.success("SUCCESS WE GOT EM ALL SON")
                succ = True
                break
        if not succ:
            expected_replies = set(ip_vk_dict.keys())
            expected_replies.remove(os.getenv('HOST_IP'))
            missing_replies = expected_replies - n.reply_ids
            log.fatal("DID NOT GET FULL SET OF REPLIES!!! Missing: \n{}".format(missing_replies))


    log = get_logger('Node')
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx = zmq.asyncio.Context()

    node = RouterAuth(sk=sk, use_auth=use_auth, loop=loop, ctx=ctx)

    loop.run_until_complete(asyncio.gather(
        node.listen(),
        send_request(node),
        check_succ(node)
    ))
    log.critical("EVENT LOOP SHOULD NOT FINISH!!!! NOOOOOOO")

class TestAuthRouter(BaseTestCase):

    log = get_logger(__name__)
    config_file = join(dirname(cilantro_ee.__path__[0]), 'vmnet_configs', 'cilantro_ee-nodes-8.json')
    enable_ui = True
    USE_AUTH = True

    def callback(self, data):
        for s in data:
            d = json.loads(s)
            if not self.nodes_got_ip.get(d['hostname']):
                self.nodes_got_ip[d['hostname']] = set()
            self.nodes_got_ip[d['hostname']].add(d['vk'])
        for hostname in self.all_hostnames:
            if self.nodes_got_ip.get(hostname) != self.all_vks:
                return
        self.end_test()

    def timeout(self):
        for hostname in self.all_hostnames:
            self.assertEqual(self.nodes_got_ip[hostname], self.all_vks)

    def test_auth_router(self):
        self.ip_vk_dict = {
            '172.29.0.1': (TESTNET_MASTERNODES[0]['vk'], TESTNET_MASTERNODES[0]['sk']),
            '172.29.0.2': (TESTNET_MASTERNODES[1]['vk'], TESTNET_MASTERNODES[1]['sk']),
            '172.29.0.3': (TESTNET_WITNESSES[0]['vk'], TESTNET_WITNESSES[0]['sk']),
            '172.29.0.4': (TESTNET_WITNESSES[1]['vk'], TESTNET_WITNESSES[1]['sk']),
            '172.29.0.5': (TESTNET_DELEGATES[0]['vk'], TESTNET_DELEGATES[0]['sk']),
            '172.29.0.6': (TESTNET_DELEGATES[1]['vk'], TESTNET_DELEGATES[1]['sk']),
            '172.29.0.7': (TESTNET_DELEGATES[2]['vk'], TESTNET_DELEGATES[2]['sk']),
            '172.29.0.8': (TESTNET_DELEGATES[3]['vk'], TESTNET_DELEGATES[3]['sk']),
            # '172.29.0.9999': (TESTNET_DELEGATES[3]['vk'], TESTNET_DELEGATES[3]['sk'])
        }

        for i, ip in enumerate(self.ip_vk_dict):
            vk, sk = self.ip_vk_dict[ip][0], self.ip_vk_dict[ip][1]
            self.execute_python("node_{}".format(i+1), wrap_func(
                nodefn, sk=sk, ip_vk_dict=self.ip_vk_dict,
                expected_ip=ip, use_auth=self.USE_AUTH))

        # file_listener(self, self.callback, self.timeout, 90)
        input('Terminate')

if __name__ == '__main__':
    unittest.main()
