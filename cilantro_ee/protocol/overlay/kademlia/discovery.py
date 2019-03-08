import zmq, zmq.asyncio, asyncio, traceback
import uuid
from cilantro_ee.constants.conf import CilantroConf
from cilantro_ee.constants.overlay_network import *
from cilantro_ee.protocol.utils.socket import SocketUtil
from cilantro_ee.protocol.overlay.kademlia.ip import *
from cilantro_ee.constants.ports import DISCOVERY_PORT
from cilantro_ee.logger import get_logger
from cilantro_ee.storage.vkbook import VKBook


class Discovery:

    def __init__(self, vk, zmq_ctx):
        self.log = get_logger('OS.Discovery')
        self.vk  = vk
        self.ctx = zmq_ctx
        self.host_ip = CilantroConf.HOST_IP
        # these part of genesis scripts?
        self.port = DISCOVERY_PORT
        self.pepper = PEPPER.encode()

        self.url = 'tcp://*:{}'.format(self.port)
        self.sock = SocketUtil.create_socket(self.ctx, zmq.ROUTER)
        # self.sock.setsockopt(zmq.IDENTITY, '{}:{}'.format(self.host_ip, self.port).encode())
        # raghu make sure this is the only socket with just ip alone as the identity
        self.sock.setsockopt(zmq.IDENTITY, self.host_ip.encode())
        self.sock.bind(self.url)

        self.is_debug = False          # turn this on for verbose messages to debug

        self.is_masternode = False
        self.is_listen_ready = False
        # raghu TODO - #enh maintain a list of ips serviced with a relative time counter to deny dos attacks ?
        # raghu TODO #enh separate out vkbook - again through genesis script?
        if VKBook.is_node_type('masternode', self.vk):
            self.is_masternode = True
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
            await req.send_multipart([ip, self.pepper])
            return True

        except zmq.ZMQError as e:
            if self.is_debug or (e.errno != zmq.EHOSTUNREACH):
                self.log.warning("ZMQError in sending discovery request to {}: {}".format(ip, e))
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

    async def _try_discover_nodes(self, req, dis_nodes, connections, requests, ip_list):
        assert len(ip_list) >= MIN_DISCOVERY_NODES, "Don't have enough discoverable addresses"
        num_requests = len(requests)
        num_replies = len(dis_nodes)
        for ip in ip_list:
            if (ip == self.host_ip) or ip in dis_nodes:
                continue
            while (num_replies < num_requests):
                is_reply = await self.try_process_reply(req, dis_nodes)
                if not is_reply:
                    break
                num_replies += 1
                if num_replies >= MIN_DISCOVERY_NODES:
                    return True

            if ip not in connections:
                url = 'tcp://{}:{}'.format(ip, self.port)
                req.connect(url)
                connections.add(ip)
            
            if ip not in dis_nodes:
                is_sent = await self.request(req, ip.encode())
                if is_sent and ip not in requests:
                    num_requests += 1
                    requests.add(ip)

        if self.is_debug:
            self.log.debug("Sent discovery request to all ips ({} {}) Sleeping for {}".format(num_requests, num_replies, DISCOVERY_WAIT))
        await asyncio.sleep(DISCOVERY_WAIT)
        while (num_replies < num_requests) and (num_replies < MIN_DISCOVERY_NODES):
            is_reply = await self.try_process_reply(req, dis_nodes)
            if not is_reply:
                return False
            num_replies += 1
        return (num_replies >= MIN_DISCOVERY_NODES)

    async def try_discover_nodes(self, dis_nodes, ip_list):
        req = SocketUtil.create_socket(self.ctx, zmq.ROUTER)
        req.setsockopt(zmq.ROUTER_MANDATORY, 1)
        event_id = uuid.uuid4().hex
        req.setsockopt(zmq.IDENTITY, '{}:{}'.format(self.host_ip, event_id).encode())
        # raghu TODO set hwm and bunch the requests to make sure they are under hwm
        # raghu TODO better strategy is to use PROBE flag rather than multiple sends

        connections = set()
        requests = set()
        try_count = 0
        is_done = False
        while not is_done and try_count < DISCOVERY_RETRIES:
            # raghu this try and except is redundant?
            try_count += 1
            try:
                is_done = await self._try_discover_nodes(req, dis_nodes, connections, requests, ip_list)
            except Exception as e:
                self.log.warning("Got exception in discovering process '{}'".format(e))

        req.close()


    async def discover_nodes(self):
        await asyncio.sleep(1)      # just to yield so listen can start before this one
        dis_nodes = {}
        if (self.is_masternode and len(VKBook.get_masternodes()) == 1):
            self.log.info('Bootstrapping as the only masternode.')
        else:
            if len(CilantroConf.BOOTNODES) > 0: # TODO refine logic post-anarchy-net
                self.log.info('Connecting to boot nodes: {}'.format(CilantroConf.BOOTNODES))
                ip_list = CilantroConf.BOOTNODES
            else:
                start_ip = self.host_ip   # TODO see if we can get a list based on env variable here
                ip_list = start_ip if type(start_ip) == list else get_ip_range(start_ip)
                self.log.info('Connecting to this ip-range: {} to {}'.format(ip_list[0], ip_list[-1]))
            iter = 0
            while iter < DISCOVERY_ITER:
                self.log.info('Trying to discover network ..')
                await self.try_discover_nodes(dis_nodes, ip_list)
                if (len(dis_nodes) >= MIN_DISCOVERY_NODES) or self.is_masternode:
                    break
                await asyncio.sleep(DISCOVERY_LONG_WAIT)
                iter += 1

            if (len(dis_nodes) < MIN_DISCOVERY_NODES) and not self.is_masternode:
                self.log.critical('''
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
x   DISCOVERY FAILED: Cannot find enough nodes ({}/{})
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
            '''.format(len(dis_nodes), MIN_DISCOVERY_NODES))
                raise Exception('Failed to discover any nodes. Killing myself with shame!')

        self.log.success("DISCOVERY COMPLETE")
        self.is_listen_ready = True

        if self.host_ip in dis_nodes:
            del dis_nodes[self.host_ip]
        return dis_nodes

