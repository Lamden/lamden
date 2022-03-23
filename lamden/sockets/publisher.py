import zmq
from string import ascii_uppercase as uppercase
import zmq.asyncio
import asyncio
from lamden.logger.base import get_logger
from contracting.db.encoder import encode

class Publisher():
    def __init__(
        self,
        ctx: zmq.Context,
        logger=None,
        testing=False,
        debug=False      
    ):        
        # Configure the listening socket
        self.log = logger or get_logger("PUBLISHER")
        self.address = None
        
        self.socket = None
        self.ctx = ctx
        self.running = False

        self.debug_published = []

        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def setup_socket(self):
        if self.running:
            self.log.warning(f'[PUBLISHER] Already running.')
            print(f'[{self.log.name}][PUBLISHER] Already running.')
            return

        self.socket = self.ctx.socket(zmq.PUB)

        self.log.info(f'[PUBLISHER] Starting on {self.address}')
        print(f'[{self.log.name}][PUBLISHER] Starting on {self.address}')

        self.running = True
        self.socket.bind(self.address)
    
    def publish(self, topic, msg):
        if not self.running:
            self.log.error(f'[PUBLISHER] Publisher is not running.')
            print(f'[{self.log.name}][PUBLISHER] Publisher is not running.')

            return

        self.log.error(f'[PUBLISHER] Publishing: {msg}')
        print(f'[{self.log.name}][PUBLISHER] Publishing: {msg}')
        self.debug_published.append(msg)

        m = encode(msg).encode()        
        self.socket.send_string(topic, flags=zmq.SNDMORE)
        self.socket.send(m)

    def announce_new_peer_connection(self, vk, ip):
        topic = "new_peer_connection"
        msg = {
            'vk': vk,
            'ip': ip
        }

        self.publish(
            topic=topic,
            msg=msg
        )
    
    def stop(self):
        if self.running:
            self.running = False

            self.log.info('[PUBLISHER] Stopping.')
            print(f'[{self.log.name}][PUBLISHER] Stopping.')

            try:
                self.socket.close()
            except zmq.ZMQError:
                pass


        