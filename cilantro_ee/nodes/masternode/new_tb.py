from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.services.overlay.network import NetworkParameters, ServiceType
from cilantro_ee.nodes.masternode.rate_limiter import RateLimiter

from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType

import zmq.asyncio
from multiprocessing import Queue
import asyncio


class TransactionBatcher:
    def __init__(self,
                 wallet: Wallet,
                 ctx: zmq.asyncio.Context,
                 socket_base,
                 ipc='ipc:///tmp/tx_batch_informer',
                 network_parameters=NetworkParameters(),
                 queue: Queue=Queue(),
                 poll_timeout=250):

        self.wallet = wallet
        self.ctx = ctx
        self.queue = queue
        self.poll_timeout = poll_timeout

        self.socket_base = socket_base
        self.network_parameters = network_parameters

        # Create publisher socket for delegates to listen to as new transaction batches come in
        self.pub = self.ctx.socket(zmq.PUB)
        self.pub.bind(self.network_parameters.resolve(socket_base=socket_base,
                                                      service_type=ServiceType.TX_BATCHER,
                                                      bind=True))

        self.pair = self.ctx.socket(zmq.PAIR)
        self.pair.connect(ipc)

        self.rate_limiter = RateLimiter(queue=self.queue, wallet=self.wallet)

        self.running = False

    async def start(self):
        asyncio.ensure_future(self.get_burn_input_hashes())
        asyncio.ensure_future(self.compose_transactions())
        self.running = True

    async def get_burn_input_hashes(self):
        while self.running:
            event = await self.pair.poll(timeout=self.poll_timeout, flags=zmq.POLLIN)
            await asyncio.sleep(0)
            if event:
                msg = await self.pair.recv()
                msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(message=msg)

                if msg_type == MessageType.BURN_INPUT_HASHES:
                    self.rate_limiter.remove_batch_ids(msg.inputHashes)

    async def compose_transactions(self):
        while self.running:
            mtype, msg = await self.rate_limiter.get_next_batch_packed()
            self.pub.send(mtype + msg)

