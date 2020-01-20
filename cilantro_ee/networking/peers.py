import asyncio
import json
from functools import partial

import zmq
from cilantro_ee.constants.ports import PEPPER
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.sockets import services
from cilantro_ee.networking import discovery


class KTable:
    def __init__(self, data: dict, initial_peers={}, response_size=10):
        self.data = data
        self.peers = initial_peers
        self.response_size = response_size

    @staticmethod
    def distance(string_a, string_b):
        int_val_a = int(string_a.encode().hex(), 16)
        int_val_b = int(string_b.encode().hex(), 16)
        return int_val_a ^ int_val_b

    def find(self, key):
        if key in self.data:
            return self.data
        elif key in self.peers:
            return {
                key: self.peers[key]
            }
        else:
            # Do an XOR sort on all the keys to find neighbors
            sort_func = partial(self.distance, string_b=key)
            closest_peer_keys = sorted(self.peers.keys(), key=sort_func)

            # Only keep the response size number
            closest_peer_keys = closest_peer_keys[:self.response_size]

            # Dict comprehension
            neighbors = {k: self.peers[k] for k in closest_peer_keys}

            return neighbors


class PeerServer(services.RequestReplyService):
    def __init__(self, socket_id: services.SocketStruct,
                 event_address: services.SocketStruct,
                 table: KTable, wallet: Wallet, ctx=zmq.Context,
                 linger=500, poll_timeout=10):

        super().__init__(socket_id=socket_id,
                         wallet=wallet,
                         ctx=ctx,
                         linger=linger,
                         poll_timeout=poll_timeout)

        self.table = table

        self.event_service = services.SubscriptionService(ctx=self.ctx)
        self.event_address = event_address
        self.event_publisher = self.ctx.socket(zmq.PUB)
        self.event_publisher.bind(str(self.event_address))

        self.event_queue_loop_running = False

    def handle_msg(self, msg):
        msg = msg.decode()
        command, args = json.loads(msg)

        if command == 'find':
            response = self.table.find(args)
            response = json.dumps(response, cls=services.SocketEncoder).encode()
            return response
        if command == 'join':
            vk, ip = args # unpack args
            asyncio.ensure_future(self.handle_join(vk, ip))
            return None
        #if command == 'ping':
        #    return self.ping_response

    async def handle_join(self, vk, ip):
        result = self.table.find(vk)

        if vk not in result or result[vk] != ip:
            # Ping discovery server
            _, responded_vk = await discovery.ping(services._socket(ip),
                                                   pepper=PEPPER.encode(), ctx=self.ctx, timeout=500)

            await asyncio.sleep(0)
            if responded_vk is None:
                return

            if responded_vk.hex() == vk:
                # Valid response
                self.table.peers[vk] = ip

                # Publish a message that a _new node has joined
                msg = ['join', (vk, ip)]
                jmsg = json.dumps(msg, cls=services.SocketEncoder).encode()
                await self.event_publisher.send(jmsg)

                second_msg = json.dumps({'event': 'node_online', 'vk': vk, 'ip': services._socket(ip).id}, cls=services.SocketEncoder).encode()
                await self.event_publisher.send(second_msg)

    async def process_event_subscription_queue(self):
        self.event_queue_loop_running = True

        while self.event_queue_loop_running:
            if len(self.event_service.received) > 0:
                message, sender = self.event_service.received.pop(0)
                msg = json.loads(message.decode())

                # Ignore event dictionaries
                if isinstance(msg, dict):
                    continue

                command, args = msg
                vk, ip = args

                if command == 'join':
                    asyncio.ensure_future(self.handle_join(vk=vk, ip=ip))

                elif command == 'leave':
                    # Ping to make sure the node is actually offline
                    _, responded_vk = await discovery.ping(ip, pepper=PEPPER.encode(),
                                                           ctx=self.ctx, timeout=500)

                    # If so, remove it from our table
                    if responded_vk is None:
                        del self.table[vk]

            await asyncio.sleep(0)

    async def start(self):
        asyncio.ensure_future(asyncio.gather(
            self.serve(),
            self.event_service.serve(),
            self.process_event_subscription_queue()
        ))
        #log.info('Peer services running on {}'.format(self.address))
        #log.info('Event services running on {}'.format(self.event_address))

    def stop(self):
        self.running = False
        self.event_queue_loop_running = False
        self.event_service.running = False
        self.event_service.stop()
