import asyncio
import json

import zmq

from cilantro_ee.sockets.inbox import AsyncInbox
from cilantro_ee.sockets import pubsub
from cilantro_ee.sockets import reqrep
from cilantro_ee.sockets import struct
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.networking import discovery, parameters

from cilantro_ee.logger.base import get_logger


class PeerServer(AsyncInbox):
    def __init__(self, socket_id: struct.SocketStruct,
                 event_address: struct.SocketStruct,
                 table: dict, wallet: Wallet, ctx=zmq.Context,
                 linger=500, poll_timeout=10, debug=False):

        super().__init__(socket_id=socket_id,
                         wallet=wallet,
                         ctx=ctx,
                         linger=linger,
                         poll_timeout=poll_timeout)

        self.table = table

        self.event_service = pubsub.SubscriptionService(ctx=self.ctx)
        self.event_address = event_address
        self.event_publisher = self.ctx.socket(zmq.PUB)
        self.event_publisher.bind(str(self.event_address))

        self.event_queue_loop_running = False

        self.params = parameters.NetworkParameters()

        self.log = get_logger('PeerService')
        self.log.propagate = debug

    def get_vk(self, vk):
        if self.table.get(vk) is not None:
            return {vk: self.table.get(vk)}
        return self.table

    async def handle_msg(self, _id, msg):
        self.log.info(f'Got msg: {msg}')
        msg = msg.decode()
        command, args = json.loads(msg)

        if command == 'find':
            response = self.get_vk(args)
            response = json.dumps(response, cls=struct.SocketEncoder).encode()
            await self.return_msg(_id, response)
        if command == 'join':
            vk, ip = args  # unpack args
            asyncio.ensure_future(self.handle_join(vk, ip))
            await self.return_msg(_id, b'ok')
        if command == 'ask':
            await self.return_msg(_id, json.dumps(self.table, cls=struct.SocketEncoder).encode())

    async def handle_join(self, vk, ip):
        result = self.get_vk(vk)

        self.log.info(f'VK {vk} from ip {ip} joining...')

        if vk not in result or result[vk] != ip:
            # Ping discovery server

            ip = self.params.resolve(ip, parameters.ServiceType.DISCOVERY)

            _, responded_vk = await discovery.ping(ip, pepper=parameters.PEPPER.encode(), ctx=self.ctx, timeout=1000)

            await asyncio.sleep(0)
            if responded_vk is None:
                self.log.info(f'{vk} never responded...')
                return

            if responded_vk.hex() == vk:
                # Valid response
                ip = struct.strip_service(str(ip))
                self.log.info(f'{vk} has joined the network as {ip}')
                self.table[vk] = ip

                # Publish a message that a _new node has joined
                msg = ['join', (vk, ip)]
                jmsg = json.dumps(msg, cls=struct.SocketEncoder).encode()
                await self.event_publisher.send(jmsg)

    async def process_event_subscription_queue(self):
        self.event_queue_loop_running = True

        while self.event_queue_loop_running:
            if len(self.event_service.received) > 0:
                message, sender = self.event_service.received.pop(0)
                msg = json.loads(message.decode())

                command, args = msg
                vk, ip = args

                if command == 'join':
                    asyncio.ensure_future(self.handle_join(vk=vk, ip=ip))

                elif command == 'leave':
                    # Ping to make sure the node is actually offline
                    _, responded_vk = await discovery.ping(ip, pepper=parameters.PEPPER.encode(),
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

    def stop(self):
        self.running = False
        self.event_queue_loop_running = False
        self.event_service.running = False
        self.event_service.stop()
        #self.socket.close()
