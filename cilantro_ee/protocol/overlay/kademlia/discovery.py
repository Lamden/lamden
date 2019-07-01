import zmq.asyncio
from cilantro_ee.protocol.overlay.kademlia.ip import *
from cilantro_ee.logger.base import get_logger
from cilantro_ee.protocol.wallet import Wallet, _verify
from cilantro_ee.protocol.comm import services

log = get_logger('DiscoveryService')

'''
DiscoverServer
Returns a message of the signed pepper and VK
'''


class DiscoveryServer(services.RequestReplyService):
    def __init__(self, address: str, wallet: Wallet, pepper: bytes, ctx=zmq.asyncio.Context()):
        super().__init__(address=address, wallet=wallet, ctx=ctx)

        self.pepper = pepper
        self.response = self.wallet.verifying_key() + self.wallet.sign(self.pepper)

    def handle_msg(self, msg):
        return self.response


def verify_vk_pepper(msg: bytes, pepper: bytes):
    if msg is None:
        return False

    assert len(msg) > 32, 'Message must be longer than 32 bytes.'
    vk, signed_pepper = unpack_pepper_msg(msg)
    return _verify(vk, pepper, signed_pepper)


def unpack_pepper_msg(msg: bytes):
    return msg[:32], msg[32:]


async def ping(ip: str, pepper: bytes, ctx: zmq.Context, timeout):
    response = await services.get(ip, msg=b'', ctx=ctx, timeout=timeout)

    if verify_vk_pepper(response, pepper):
        log.info('Verifying key successfully extracted and message matches network pepper.')
        vk, _ = unpack_pepper_msg(response)
        return ip, vk

    return ip, None


async def discover_nodes(ip_list, pepper: bytes, ctx: zmq.Context, timeout=3000, retries=10):
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

