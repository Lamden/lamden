import asyncio
import threading
import zmq
import zmq.auth
from lamden.logger.base import get_logger

class Subscriber():
    def __init__(
        self,
        _address: str,  # example: "tcp://localhost:6000"
        _topics = [''],
        _callback = None,
        _ctx = zmq.Context.instance(),
        logger=None
    ):
        self.log = logger or get_logger("SUBSCRIBER")
        # Configure the listening socket
        self.running = False
        self.address = _address
        self.ctx = _ctx

        self.socket = self.ctx.socket(zmq.SUB)

        self.topics = _topics
        self.callback = _callback
        self.sub_task = None

        self.debug_events = []

    def start(self, loop):
        try:
            self.socket.connect(self.address)
        except zmq.error.Again as error:
            self.log.error(error)
            # socket.close()
            return False
        # asyncio.create_task(self.subscriber_thread())
        # self.sub_task = loop.run_until_complete(self.subscriber_thread())
        print('subscriber start')
        self.sub_task = threading.Thread(target=self.start2, args=[loop])
        self.sub_task.start()
        return True

    def start2(self, loop):
        print('subscriber start2')
        loop.run_until_complete(self.subscriber_thread())
        
    def add_topic(self, topic):
        self.socket.setsockopt(zmq.SUBSCRIBE, (topic.encode('utf8')))

    async def subscriber_thread(self):      
        # print("starting subscriber_thread")
        for topic in self.topics:
            self.socket.setsockopt(zmq.SUBSCRIBE, (topic.encode('utf8')))
            self.log.info(f'[SUBSCRIBER] Subscribed to topic "{topic}" on {self.address}')
            print(f'[{self.log.name}][SUBSCRIBER] Subscribed to topic "{topic}" on {self.address}')

        self.running = True    
        while self.running:
            try:
                event = self.socket.poll(timeout=50, flags=zmq.POLLIN)
            except zmq.error.ZMQError:
                self.socket.close()
                self.running = False
                return

            if(event):
                try:
                    data = self.socket.recv_multipart()
                    self.debug_events.append(data)

                    self.log.info(f'[SUBSCRIBER] Got event from {self.address}')
                    print(f'[{self.log.name}][SUBSCRIBER] Got event from {self.address}')

                    if(self.callback):
                        await self.callback(data)
                except zmq.ZMQError as e:
                    if e.errno == zmq.ETERM:
                        break           # Interrupted
                    else:
                        raise

            await asyncio.sleep(0)

        self.socket.close()
        # print("subscriber finished")


    def stop(self):
        if self.running:
            self.log.info('[SUBSCRIBER] Stopping.')
            print(f'[{self.log.name}][SUBSCRIBER] Stopping.')

            self.socket.close()
            if self.sub_task:
                try:
                    self.sub_task.join()
                except RuntimeError:
                    pass
                self.sub_task = None
            self.running = False
