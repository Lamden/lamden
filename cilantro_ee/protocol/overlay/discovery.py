import zmq, zmq.asyncio, asyncio, traceback
from cilantro_ee.constants.overlay_network import *
from cilantro_ee.constants.conf import CilantroConf
from cilantro_ee.constants.ports import DISCOVERY_PORT
from cilantro_ee.protocol.overlay.ip import *
from cilantro_ee.protocol.overlay.auth import Auth
from cilantro_ee.logger import get_logger
from cilantro_ee.storage.vkbook import VKBook


class Discovery:
    log = get_logger('Discovery')
    host_ip = CilantroConf.HOST_IP
    port = DISCOVERY_PORT
    url = 'tcp://*:{}'.format(port)
    pepper = PEPPER.encode()
    discovered_nodes = {}
    connections = {}
    is_setup = False
    is_listen_ready = False
    bootnodes = CilantroConf.BOOTNODES

    @classmethod
    def setup(cls, ctx=None):
        if not cls.is_setup:
            cls.is_setup = True
            cls.ctx = ctx or zmq.asyncio.Context()
            cls.sock = cls.ctx.socket(zmq.ROUTER)
            cls.sock.setsockopt(zmq.IDENTITY, cls.host_ip.encode())
            cls.is_connected = False

            # DEBUG -- TODO DELETE
            cls.log.important("my vk: {}".format(Auth.vk))
            cls.log.important("is masternode: {}".format(VKBook.is_node_type('masternode', Auth.vk)))
            # END DEBUG

            if VKBook.is_node_type('masternode', Auth.vk):
                # cls.discovered_nodes[Auth.vk] = cls.host_ip
                cls.is_master_node = True
                cls.is_listen_ready = True
            else:
                cls.log.info("This node is not a masternode")

    @classmethod
    async def listen(cls):
        cls.sock.bind(cls.url)
        cls.log.info('Listening to other nodes on {}'.format(cls.url))
        # if cls.is_listen_ready:
            # await asyncio.sleep(3)
        while True:
            try:
                msg = await cls.sock.recv_multipart()
                cls.log.spam("Got msg over discovery socket: {}".format(msg))
                # cls.log.info("Got msg over discovery socket: {}".format(msg))  # TODO remove
                ip, pepper = msg[:2]

                if pepper != cls.pepper:
                    cls.log.warning("Node with ip {} tried to connect using incorrect pepper {}!".format(ip, pepper))
                    continue

                if len(msg) == 2:
                    cls.reply(ip)
                elif len(msg) == 3:
                    vk = msg[-1]
                    cls.discovered_nodes[vk.decode()] = ip.decode()
                    cls.is_listen_ready = True

            except Exception as e:
                cls.log.error(traceback.format_exc())

    @classmethod
    async def discover_nodes(cls, start_ip):
        is_masternode = VKBook.is_node_type('masternode', Auth.vk)
        try_count = 0

        cls.log.info('We have the following boot nodes: {}'.format(cls.bootnodes))

        await asyncio.sleep(1)
        while True:
            if len(cls.bootnodes) > 0: # TODO refine logic post-anarchy-net
                cls.connect(cls.bootnodes)
            else:
                cls.connect(get_ip_range(start_ip))
            try_count += 1
            if (is_masternode and len(VKBook.get_masternodes()) == 1) or \
                    (len(cls.discovered_nodes) == 0 and is_masternode and cls.is_connected and try_count >= RETRIES_BEFORE_SOLO_BOOT):
                cls.log.important('Bootstrapping as the only masternode. (num_discovered={})'
                                  .format(len(cls.discovered_nodes)))
                cls.discovered_nodes[Auth.vk] = cls.host_ip
                return True
            elif len(cls.discovered_nodes) >= MIN_BOOTSTRAP_NODES:
                cls.log.info('Found {} nodes to bootstrap: {}'.format(
                    len(cls.discovered_nodes), cls.discovered_nodes
                ))
                return True
            # elif try_count >= DISCOVERY_RETRIES:
            #     cls.log.info('Did not find enough nodes after {} tries ({}/{}).'.format(
            #         try_count,
            #         len(cls.discovered_nodes),
            #         MIN_BOOTSTRAP_NODES
            #     ))
            #     return False

            await asyncio.sleep(DISCOVERY_TIMEOUT)

    # raghu these class methods are not thread-safe. Not sure why we want them to be class methods rather than instance methods
#    @classmethod
#    async def discover_nodes(cls, start_ip):
#        try_count = 0
#        cls.log.info('Connecting to this ip-range: {}'.format(start_ip))
#        ips = get_ip_range(start_ip)
#        while try_count < DISCOVERY_RETRIES:
#            try_count += 1
#            for ip in ips:
#                if ip in cls.connections:
#                    continue
#                url = 'tcp://{}:{}'.format(ip, cls.port)
#                cls.sock.connect(url)
#                cls.connections[ip] = url
#                cls.request(ip.encode())
#                if (len(cls.discovered_nodes) == 1 and Auth.vk in VKBook.get_masternodes()) \
#                    and try_count >= 2:
#                    cls.log.important('Bootstrapping as the only masternode.'.format(
#                        len(cls.discovered_nodes)
#                    ))
#                    return True
#                elif len(cls.discovered_nodes) >= MIN_BOOTSTRAP_NODES:
#                    cls.log.info('Found {} nodes to bootstrap.'.format(
#                        len(cls.discovered_nodes)
#                    ))
#                    return True
#            await asyncio.sleep(DISCOVERY_TIMEOUT)
#        assert try_count >= DISCOVERY_RETRIES:
#        cls.log.info('Did not find enough nodes after {} tries ({}/{}).'.format(
#            try_count,
#            len(cls.discovered_nodes),
#            MIN_BOOTSTRAP_NODES
#        ))
#        return False

    @classmethod
    def request(cls, ip):
        # TODO this is soooo sketch wrapping this in a try/except. Why does it give a 'Could not route host' error??
        # --davis
        try:
            cls.sock.send_multipart([ip, cls.pepper])
        except Exception as e:
            cls.log.warning("Got ZMQError sending discovery msg\n{}".format(e))

    @classmethod
    def reply(cls, ip):
        # cls.log.important2("discovered nodes so far: {}".format(cls.discovered_nodes))  # TODO remove
        # cls.log.important("Attempting to replying to IP {} ... is_listen_ready={}".format(ip, cls.is_listen_ready))
        if cls.is_listen_ready and ip != cls.host_ip:
            cls.log.debugv("sending discovery reply to ip {}".format(ip))
            cls.sock.send_multipart([ip, cls.pepper, Auth.vk.encode()])
            cls.is_connected = True

    @classmethod
    def connect(cls, ips):
        # cls.log.important2("discovered nodes so far: {}".format(cls.discovered_nodes))  # TODO remove
        # cls.log.important("Attempting to connect to IP range {}".format(ips))  # TODO remove
        cls.log.debugv("Attempting to connect to IP range {}".format(ips[0]))
        for ip in ips:
            cls.log.spam("Attempting to connect to IP {}".format(ip))
            if ip == cls.host_ip:
                continue
            # cls.log.important("Attempting to discover IP {}".format(ip))  # TODO remove
            url = 'tcp://{}:{}'.format(ip, cls.port)
            cls.sock.connect(url)
            cls.connections[ip] = url
            cls.request(ip.encode())
