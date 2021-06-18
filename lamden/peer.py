import zmq
import json
import time
from lamden.logger.base import get_logger
import zmq.asyncio
import asyncio

WORK_SERVICE = 'work'

class Peer:
    def __init__(self, domain, socket, key, services, blacklist, max_strikes):
        self.socket = socket
        self.domain = domain
        self.key = key
        self.services = services
        self.in_consensus = True
        self.errored = False

        self.max_strikes = max_strikes
        self.strikes = 0

        self.blacklist = blacklist

        self.log = get_logger("PEER")
        self.running = False

    def start(self):
        self.running = True
        asyncio.ensure_future(self.check_subscription())

    def stop(self):
        self.running = False
        self.socket.close()

    def not_in_consensus(self):
        self.in_consensus = False

    def currently_participating(self):
        return self.in_consensus and self.running and not self.errored

    def add_strike(self):
        self.strikes += 1
        self.log.error(f'Strike {self.strikes} for peer {self.key[:8]}')
        # TODO if self.strikes == self.max_strikes then blacklist this peer or something
        if self.strikes == self.max_strikes:
            self.stop()
            self.blacklist(self.key)

    async def check_subscription(self):
        while self.running:
            try:
                event = await self.socket.poll(timeout=50, flags=zmq.POLLIN)

                if event:
                    # self.log.info("got event!")

                    data = await self.socket.recv_multipart()
                    topic, msg = data
                    if topic.decode("utf-8") == WORK_SERVICE:
                        message = json.loads(msg)
                        self.log.debug(json.dumps({
                            'type': 'tx_lifecycle',
                            'file': 'new_sockets',
                            'event': 'received_from_socket',
                            'hlc_timestamp': message['hlc_timestamp'],
                            'system_time': time.time()
                        }) + '\n')
                    await self.process_subscription(data)

            except zmq.error.ZMQError as error:
                self.log.error(error)
                self.stop()
                self.errored = True

            await asyncio.sleep(0)

    async def process_subscription(self, data):
        topic, msg = data
        services = self.services()
        processor = services.get(topic.decode("utf-8"))
        message = json.loads(msg)
        if not message:
            self.log.error(msg)
            self.log.error(message)
        if processor is not None and message is not None:
            if topic.decode("utf-8") == WORK_SERVICE:
                self.log.debug(json.dumps({
                    'type': 'tx_lifecycle',
                    'file': 'new_sockets',
                    'event': 'processing_from_socket',
                    'hlc_timestamp': message['hlc_timestamp'],
                    'system_time': time.time()
                }) + '\n')
            await processor.process_message(message)


