import zmq
import zmq.auth
from threading import Thread
import asyncio

class Subscriber():
    def __init__(
        self,
        _address: str,  # example: "tcp://localhost:6000"
        _topics = [],
        _callback = None,
        _ctx = zmq.Context.instance()
    ):        
        # Configure the listening socket
        self.running = False
        self.address = _address
        self.ctx = _ctx
        self.socket = self.ctx.socket(zmq.SUB)    
        self.topics = _topics
        self.callback = _callback
        self.sub_task = None

    def start(self, loop):
        try:
            self.socket.connect(self.address)
        except zmq.error.Again as error:
            self.log.error(error)
            # socket.close()
            return False
        self.sub_task = loop.run_until_complete(self.subscriber_thread())
        return True
        
    def add_topic(self, topic):
        self.socket.setsockopt(zmq.SUBSCRIBE, (topic.encode('utf8')))

    async def subscriber_thread(self):      
        print("starting subscriber_thread")
        for topic in self.topics:
            self.socket.setsockopt(zmq.SUBSCRIBE, (topic.encode('utf8')))
        self.running = True    
        while self.running:
            event = self.socket.poll(timeout=50, flags=zmq.POLLIN)
            if(event):
                try:
                    data = self.socket.recv_multipart()    
                    # print(data)
                    if(self.callback):
                        await self.callback(data)
                except zmq.ZMQError as e:
                    if e.errno == zmq.ETERM:
                        break           # Interrupted
                    else:
                        raise

    def stop(self):
        self.running = False
        self.sub_task.cancel()
        self.socket.close()
        self.ctx.term()
