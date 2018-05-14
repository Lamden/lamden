from cilantro.logger import get_logger
from cilantro.protocol.networks import *
from cilantro.protocol.networks.ip_util import *
import asyncio, zmq, zmq.asyncio, time, resource, uuid

SOCKET_LIMIT = 2500
resource.setrlimit(resource.RLIMIT_NOFILE, (SOCKET_LIMIT, SOCKET_LIMIT))

class Discovery:
    def __init__(self, context, port=31337):
        self.context = context
        self.port = port
        self.log = get_logger("Crawler")

    def listen_for_crawlers(self):
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind("tcp://*:{}".format(self.port))
        self.log.debug('Listening to the world on port {}...'.format(self.port))
        time.sleep(0.1)
        return asyncio.ensure_future(self._listen_for_crawlers())

    async def _listen_for_crawlers(self):
        while True:
            msg = await self.socket.recv()
            if not msg: continue
            msg_type, data = decode_msg(msg)
            if data != []:
                self.log.debug("Received - {}: {}".format(msg_type, data))
            self.socket.send(compose_msg('ack'))

    def discover(self, mode='neighborhood'):
        ips = {}
        if mode == 'test':
            host = os.getenv('HOST_IP', '127.0.0.1')
            ips[host] = [decimal_to_ip(d) for d in range(*get_local_range(host))]
        else:
            public_ip = get_public_ip()
            if mode == 'local':
                ips['localhost'] = [decimal_to_ip(d) for d in range(*get_local_range(public_ip))]
            elif mode == 'neighborhood':
                for ip in get_region_range(public_ip):
                    ips[ip] = [decimal_to_ip(d) for d in range(*get_local_range(ip))]
        self.log.debug('Scanning using {} mode...'.format(mode))
        results = []
        for host in ips:
            results += self.scan_all(ips[host])
        self.discovered_nodes = results
        self.log.debug(self.discovered_nodes)
        self.log.debug('Done with discovery scan.')
        return results

    def scan_all(self, ips, poll_time=250):
        sockets = []
        results = []
        poller = zmq.Poller()
        for ip in ips:
            url = "tcp://{}:{}".format(ip, self.port)
            sock = self.context.socket(zmq.REQ)
            sock.linger = 0
            sock.connect(url)
            sockets.append({
                'socket': sock,
                'ip':ip
            })
            sock.send(compose_msg('discover'), zmq.NOBLOCK)
            poller.register(sock, zmq.POLLIN)

        evts = dict(poller.poll(poll_time))
        for s in sockets:
            sock = s['socket']
            ip = s['ip']
            if sock in evts:
                try:
                    msg = sock.recv(zmq.NOBLOCK)
                    self.log.debug("{} is online".format(ip))
                    results.append(ip)
                except zmq.Again:
                    break
        return results
