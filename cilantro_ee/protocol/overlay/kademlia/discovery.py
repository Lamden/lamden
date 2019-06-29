import zmq
import zmq.asyncio
from cilantro_ee.protocol.overlay.kademlia.ip import *
from cilantro_ee.logger.base import get_logger
from cilantro_ee.protocol.wallet import Wallet, _verify
from cilantro_ee.constants.ports import DISCOVERY_PORT

log = get_logger('DiscoveryService')

'''
DiscoverServer
Returns a message of the signed pepper and VK
'''


class RequestReplyService:
    def __init__(self, address: str, wallet: Wallet, ctx: zmq.Context, linger=2000, poll_timeout=2000):
        self.address = address
        self.wallet = wallet
        self.ctx = ctx

        self.socket = None

        self.linger = linger
        self.poll_timeout = poll_timeout

        self.running = False

    async def serve(self):
        self.socket = self.ctx.socket(zmq.REP)
        self.socket.setsockopt(zmq.LINGER, self.linger)
        self.socket.bind(self.address)

        self.running = True

        while self.running:
            event = await self.socket.poll(timeout=self.poll_timeout, flags=zmq.POLLIN)
            if event:
                msg = await self.socket.recv()

                result = self.handle_msg(msg)

                await self.socket.send(result)

        self.socket.close()

    def handle_msg(self, msg):
        return msg

    def stop(self):
        self.running = False

class DiscoveryServer(RequestReplyService):
    def __init__(self, address: str, wallet: Wallet, pepper: bytes, ctx=zmq.asyncio.Context()):
        super().__init__(address=address, wallet=wallet, ctx=ctx)

        self.pepper = pepper
        self.response = self.wallet.verifying_key() + self.wallet.sign(self.pepper)

    def handle_msg(self, msg):
        return self.response


def verify_vk_pepper(msg: bytes, pepper: bytes):
    assert len(msg) > 32, 'Message must be longer than 32 bytes.'
    vk, signed_pepper = unpack_pepper_msg(msg)
    return _verify(vk, pepper, signed_pepper)


def unpack_pepper_msg(msg: bytes):
    return msg[:32], msg[32:]


async def ping(ip: str, pepper: bytes, ctx: zmq.Context, timeout=0.5):
    try:
        socket = ctx.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 2000)

        discovery_address = 'tcp://{}:{}'.format(ip, DISCOVERY_PORT)

        socket.connect(discovery_address)

        await socket.send(b'')

        log.info('Sent ping to {}. Waiting for a response.'.format(discovery_address))

        event = await socket.poll(timeout=timeout*1000, flags=zmq.POLLIN)

        if event:
            msg = await socket.recv()

            log.info('Got response to ping from {}.'.format(ip))

            vk, _ = unpack_pepper_msg(msg)

            if verify_vk_pepper(msg, pepper):
                log.info('Verifying key successfully extracted and message matches network pepper.')
                return ip, vk

            log.info('Message could not be verified. Either incorrect signature, or wrong network pepper.')
            return ip, None

        else:
            log.info('Ping timeout. No response from {}.'.format(ip))
            return ip, None
    except Exception as e:
        log.critical('Exception raised while pinging! {}'.format(str(e)))
        return ip, None


async def discover_nodes(ip_list, pepper: bytes, ctx: zmq.Context, timeout=3, retries=10):
    nodes_found = {}
    one_found = False
    retries_left = retries

    while not one_found and retries_left > 0:
        tasks = [ping(ip=ip, pepper=pepper, ctx=ctx, timeout=timeout) for ip in ip_list]

        tasks = asyncio.gather(*tasks)
        loop = asyncio.get_event_loop()

        log.info('Sending pings to {} nodes.'.format(len(ip_list)))

        if loop.is_running():
            results = await asyncio.ensure_future(tasks)
        else:
            results = loop.run_until_complete(tasks)

        for res in results:
            ip, vk = res
            if vk is not None:
                nodes_found[ip] = vk.hex()
                one_found = True

        if not one_found:
            retries_left -= 1
            log.info('No one discovered... {} retried left.'.format(retries_left))

    # Returns mapping of IP -> VK. VKs that return None are not stored in the dictionary.
    return nodes_found

