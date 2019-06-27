import zmq, zmq.asyncio, asyncio, traceback
import uuid

from datetime import datetime, timedelta

from cilantro_ee.constants.overlay_network import *
from cilantro_ee.protocol.utils.socket import SocketUtil
from cilantro_ee.protocol.overlay.kademlia.ip import *
from cilantro_ee.constants.ports import DISCOVERY_PORT
from cilantro_ee.logger import get_logger
from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.constants import conf

from cilantro_ee.protocol.wallet import Wallet, _verify

class Discovery:

    def __init__(self, vk, zmq_ctx,
                 host_ip=conf.HOST_IP,
                 port=DISCOVERY_PORT,
                 pepper=PEPPER.encode(),
                 url=None,
                 is_debug=False):

        self.log = get_logger('OS.Discovery')

        self.vk = vk
        self.ctx = zmq_ctx
        self.host_ip = host_ip

        self.port = port
        self.pepper = pepper

        if url is None:
            self.url = 'tcp://*:{}'.format(self.port)
        else:
            self.url = url

        self.sock = SocketUtil.create_socket(self.ctx, zmq.ROUTER)
        # self.sock.setsockopt(zmq.IDENTITY, '{}:{}'.format(self.host_ip, self.port).encode())
        # raghu make sure this is the only socket with just ip alone as the identity

        self.sock.setsockopt(zmq.IDENTITY, self.host_ip.encode())
        self.sock.bind(self.url)

        self.is_debug = is_debug          # turn this on for verbose messages to debug

        self.is_masternode = False
        self.is_listen_ready = False
        self.min_discovery_nodes = 1 if (len(PhoneBook.masternodes) == 1) else 2

        # raghu TODO - #enh maintain a list of ips serviced with a relative time counter to deny dos attacks ?
        # raghu TODO #enh separate out vkbook - again through genesis script?

        if self.vk in PhoneBook.masternodes:
            self.is_masternode = True
            if (len(PhoneBook.masternodes) == 2):
                self.min_discovery_nodes = 1

    def set_ready(self):
        if self.is_masternode:
            self.is_listen_ready = True

    async def listen(self):
        self.log.info('Listening for other nodes to discover me')
        while True:
            try:
                msg = await self.sock.recv_multipart()

                if self.is_debug:
                    self.log.debug("Got msg over discovery socket: {}".format(msg))

                ip, pepper = msg[:2]

                if pepper != self.pepper:
                    # raghu TODO #audit #error_processing #dos - these should go into zmq blacklist
                    self.log.warning("Node with ip {} tried to connect using incorrect pepper {}!".format(ip, pepper))
                    continue

                if len(msg) == 2:
                    await self.reply(ip)

                elif len(msg) == 3:
                    self.log.warning("Shouldn't get reply to this channel, ignoring!")

            except zmq.ZMQError as e:
                self.log.warning("ZMQError '{}' in discovery\n".format(e))
            except Exception as e:
                self.log.warning("Exception '{}' in discovery".format(e))

        self.sock.close()
        self.log.fatal('Discovery DIED')

    async def request(self, req, ip):
        if self.is_debug:
            self.log.debug("Sending request to {}".format(ip))

        try:
            req.send_multipart([ip, self.pepper])
            return True

        except zmq.ZMQError as e:
            if self.is_debug or (e.errno != zmq.EHOSTUNREACH):
                self.log.warning("ZMQError in sending discovery request to {}: {}".format(ip, e))
            self.log.error('ZMQ ERROR: {}'.format(e))
            return False
        except Exception as e:
            self.log.warning("Got exception in sending discovery msg: {}".format(e))
            return False

    async def reply(self, ip):
        if self.is_listen_ready:
            # raghu TODO #dos there could be dos attack on discovery socket
            # anyone connects to this socket, we give away our vk
            # requester should send in their vk which can be verified with VKBook or something

            if self.is_debug:
                self.log.debug("Replying to {}".format(ip))

            try:
                await self.sock.send_multipart([ip, self.pepper, self.vk.encode()])

            except zmq.ZMQError as e:
                self.log.warning("ZMQError in replying to discovery msg: {}".format(e))
            except Exception as e:
                self.log.warning("Got exception in replying to discovery msg: {}".format(e))

        elif self.is_debug:
            self.log.debug("Not authorized to reply to {}".format(ip))

    async def try_process_reply(self, req, dis_nodes):
        try:
            event = await req.poll(timeout=0, flags=zmq.POLLIN)
            if event == 0:
                return False

            # at this point, we should have a message
            msg = await req.recv_multipart(zmq.DONTWAIT)
            assert len(msg) == 3, "Got something else instead of reply!"

            ip_enc, pepper = msg[:2]

            ip = ip_enc.decode()
            if self.is_debug:
                self.log.debug("Got reply from {}".format(ip))
            if ip in dis_nodes:
                return False
            vk = msg[-1]
            dis_nodes[ip] = vk.decode()
            return True

        # except zmq.ZMQError as e:
            # if e.errno != zmq.EAGAIN:
                # self.log.warning("ZMQError '{}' in discovery reply\n".format(e))
        except Exception as e:
            self.log.warning("Exception '{}' in discovery reply processing".format(e))

        return False

    async def _try_discover_nodes(self, req, dis_nodes, connections, requests):
        num_requests = len(requests)
        num_replies = len(dis_nodes)
        for ip in connections:
            while (num_replies < num_requests):
                is_reply = await self.try_process_reply(req, dis_nodes)
                if not is_reply:
                    break
                num_replies += 1
                if num_replies >= self.min_discovery_nodes:
                    return True

            if ip not in dis_nodes:
                is_sent = await self.request(req, ip.encode())
                if is_sent and ip not in requests:
                    num_requests += 1
                    requests.add(ip)

        if self.is_debug:
            self.log.debug("Sent discovery request to all ips ({} {}) Sleeping for {}".format(num_requests, num_replies, DISCOVERY_WAIT))
        await asyncio.sleep(DISCOVERY_WAIT)
        while (num_replies < num_requests) and (num_replies < self.min_discovery_nodes):
            is_reply = await self.try_process_reply(req, dis_nodes)
            if not is_reply:
                return False
            num_replies += 1
        return (num_replies >= self.min_discovery_nodes)

    async def try_discover_nodes(self, dis_nodes, ip_list):
        # Minimum Discovery Nodes needed when entire network starts at same time
        # Can we get rid of it and make it just one?
        assert len(ip_list) >= self.min_discovery_nodes, "Don't have enough discoverable addresses"

        req = SocketUtil.create_socket(self.ctx, zmq.ROUTER) # Doesn't do anything besides give us a socket with a global context

        req.setsockopt(zmq.ROUTER_MANDATORY, 1) # If errors, they will be shown

        event_id = uuid.uuid4().hex

        req.setsockopt(zmq.IDENTITY, '{}:{}'.format(self.host_ip, event_id).encode())
        # raghu TODO set hwm and bunch the requests to make sure they are under hwm
        # raghu TODO better strategy is to use PROBE flag rather than multiple sends

        connections = set()
        requests = set()
        try_count = 0
        is_done = False
        # first form connections
        for ip in ip_list:
            if (ip == self.host_ip) or ip in dis_nodes:
                continue
            if ip not in connections:
                url = 'tcp://{}:{}'.format(ip, self.port)
                req.connect(url)
                connections.add(ip)
        await asyncio.sleep(1)
        while not is_done and try_count < DISCOVERY_RETRIES:
            # raghu this try and except is redundant?
            try_count += 1
            try:
                is_done = await self._try_discover_nodes(req, dis_nodes, connections, requests)
            except Exception as e:
                self.log.warning("Got exception in discovering process '{}'".format(e))

        req.close()

    async def discover_nodes(self):
        await asyncio.sleep(1)      # just to yield so listen can start before this one
        dis_nodes = {}

        # Bootstraping into a network with a single Masternode skips the discovery process
        if self.is_masternode and len(PhoneBook.masternodes) == 1:
            self.log.info('Bootstrapping as the only masternode.')

        else:
            assert len(conf.BOOTNODES) > 0, 'You must provide initial nodes to the network!'

            self.log.info('Connecting to boot nodes: {}'.format(conf.BOOTNODES)) # Change from Bootnode to Something else
            ip_list = conf.BOOTNODES

            for _ in range(DISCOVERY_ITER):
                self.log.info('Trying to discover network ..')

                await self.try_discover_nodes(dis_nodes, ip_list)

                # found_nodes = await self.try_discover_nodes(ip_list)
                # dis_nodes.update(found_nodes)

                if len(dis_nodes) >= self.min_discovery_nodes:
                    break

                await asyncio.sleep(DISCOVERY_LONG_WAIT)

            if (len(dis_nodes) < self.min_discovery_nodes) and not self.is_masternode:
                self.log.critical('''
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
x   DISCOVERY FAILED: Cannot find enough nodes ({}/{})
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
            '''.format(len(dis_nodes), self.min_discovery_nodes))
                raise Exception('Failed to discover any nodes. Killing myself with shame!')

        self.log.success("DISCOVERY COMPLETE")
        self.is_listen_ready = True

        if self.host_ip in dis_nodes:
            del dis_nodes[self.host_ip]

        '''
        DIS_NODES = {
            '1.1.1.1': 'hex_string'
        }
        '''

        return dis_nodes

'''
DiscoverServer
Returns a message of the signed pepper and VK
'''

class DiscoveryServer:
    def __init__(self, address: str, wallet: Wallet, pepper: bytes, ctx=zmq.asyncio.Context()):
        self.address = address
        self.socket = None
        self.ctx = ctx

        self.wallet = wallet
        self.pepper = pepper
        self.response = self.wallet.verifying_key() + self.wallet.sign(self.pepper)

        self.running = False

    async def serve(self):
        self.socket = self.ctx.socket(zmq.REP)
        self.socket.bind(self.address)

        self.running = True

        while self.running:
            event = await self.socket.poll(timeout=5, flags=zmq.POLLIN)
            if event:
                await self.socket.recv()
                self.socket.send(self.response)

        self.ctx.destroy()

    def stop(self):
        self.running = False


def verify_vk_pepper(msg: bytes, pepper: bytes):
    assert len(msg) > 32, 'Message must be longer than 32 bytes.'
    vk, signed_pepper = unpack_pepper_msg(msg)
    return _verify(vk, pepper, signed_pepper)


def unpack_pepper_msg(msg: bytes):
    return msg[:32], msg[32:]


async def ping(ip: str, pepper: bytes, ctx: zmq.Context, timeout=30):
    await asyncio.sleep(0.1)
    socket = ctx.socket(zmq.REQ)
    socket.connect(ip)
    socket.send(b'')

    delta = timedelta(seconds=timeout)

    start = datetime.now()
    while True:
        event = await socket.poll(timeout=5, flags=zmq.POLLIN)
        if event:
            msg = await socket.recv()
            vk, _ = unpack_pepper_msg(msg)
            if verify_vk_pepper(msg, pepper):
                return vk, ip
            return None, ip

        if datetime.now() - start > delta:
            return None, ip

def discover_nodes(ip_list, pepper:bytes, ctx:zmq.Context, timeout=5, retries=3):

    nodes_found = {}

    tasks = [ping(ip=ip, pepper=pepper, ctx=ctx, timeout=timeout) for ip in ip_list]
    tasks = asyncio.gather(*tasks)

