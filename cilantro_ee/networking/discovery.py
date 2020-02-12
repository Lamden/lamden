import zmq.asyncio

import cilantro_ee.sockets.reqrep
import cilantro_ee.sockets.struct
from cilantro_ee.logger.base import get_logger
from cilantro_ee.crypto.wallet import Wallet, _verify
from cilantro_ee.sockets import services
import asyncio
log = get_logger('DiscoveryService')

'''
DiscoverServer
Returns a message of the signed pepper and VK
'''

TIMEOUT = 1000
LINGER = 500
POLL = 50


class DiscoveryServer(cilantro_ee.sockets.reqrep.RequestReplyService):
    def __init__(self, socket_id: cilantro_ee.sockets.struct.SocketStruct, wallet: Wallet, pepper: bytes, ctx=zmq.asyncio.Context(), **kwargs):

        super().__init__(socket_id=socket_id, wallet=wallet, ctx=ctx, **kwargs)

        self.pepper = pepper
        self.response = self.wallet.verifying_key() + self.wallet.sign(self.pepper)

    def handle_msg(self, msg):
        return self.response


def verify_vk_pepper(msg: bytes, pepper: bytes):
    if msg is None:
        return False

    if len(msg) < 32:
        return False

    vk, signed_pepper = unpack_pepper_msg(msg)
    return _verify(vk, pepper, signed_pepper)


def unpack_pepper_msg(msg: bytes):
    return msg[:32], msg[32:]


async def ping(socket_id: cilantro_ee.sockets.struct.SocketStruct, pepper: bytes, ctx: zmq.Context, timeout, debug=False):
    log = get_logger('Pinger')
    log.propagate = debug
    log.info(f'Pinging: {socket_id.zmq_url()}')
    response = await services.get(socket_id=socket_id, msg=b'', ctx=ctx, timeout=timeout)

    log.info('Got response: {}'.format(response))

    vk = None
    if verify_vk_pepper(response, pepper):
        log.info('Verifying key successfully extracted and message matches network pepper.')
        vk, _ = unpack_pepper_msg(response)

    return str(socket_id), vk


async def discover_nodes(ip_list, pepper: bytes, ctx: zmq.Context, timeout=1000, retries=10, debug=False):
    nodes_found = {}
    one_found = False
    retries_left = retries

    log = get_logger('DiscoverNodes')
    log.propagate = debug
    log.info([str(ip) for ip in ip_list])

    while not one_found and retries_left > 0:
        tasks = [ping(socket_id=ip, pepper=pepper, ctx=ctx, timeout=timeout) for ip in ip_list]

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
                nodes_found[str(ip)] = vk.hex()
                log.info(f'Found {ip} with VK {vk}')
                one_found = True

        if not one_found:
            retries_left -= 1
            log.info('No one discovered... {} retried left.'.format(retries_left))

    # Returns mapping of IP -> VK. VKs that return None are not stored in the dictionary.
    return nodes_found

