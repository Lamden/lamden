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
    
    async def publish(self, topic, msg):
        if not self.running:
            self.log.error(f'[PUBLISHER] Publisher is not running.')
            print(f'[{self.log.name}][PUBLISHER] Publisher is not running.')

            return

        self.debug_published.append(msg)

        m = encode(msg).encode()        
        self.socket.send_string(topic, flags=zmq.SNDMORE)
        self.socket.send(m)
    
    def stop(self):
        if self.running:
            self.running = False

            self.log.info('[PUBLISHER] Stopping.')
            print(f'[{self.log.name}][PUBLISHER] Stopping.')

            self.socket.close()

        