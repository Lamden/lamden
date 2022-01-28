import zmq
from string import ascii_uppercase as uppercase
import zmq.asyncio
import asyncio
from lamden.logger.base import get_logger
from contracting.db.encoder import encode

class Publisher():
    def __init__(
        self,
        socket_id, 
        ctx: zmq.Context,     
        testing=False,
        debug=False      
    ):        
        # Configure the listening socket

        self.address = socket_id
        
        self.socket = None
        self.ctx = ctx
        self.running = False 
        self.log = get_logger("PUBLISHER")

        self.debug_published = []

    def setup_socket(self): 
        if self.running:
            self.log.error('publisher.start: publisher already running')
            return
        self.socket = self.ctx.socket(zmq.PUB)
        # print('publisher.start: publisher starting on {}'.format(self.address))
        self.log.info('publisher.start: publisher starting on {}'.format(self.address))
        self.running = True
        self.socket.bind(self.address)
    
    async def publish(self, topic, msg):
        if not self.running:
            self.log.error('publisher.publish: publisher is not running')
            return

        self.debug_published.append(msg)

        m = encode(msg).encode()        
        self.socket.send_string(topic, flags=zmq.SNDMORE)
        self.socket.send(m)
    
    def stop(self):
        if self.running:
            self.running = False
            self.socket.close()

        