import asyncio
import zmq
import zmq.asyncio
import aioprocessing
from threading import Thread
from cilantro.logger import get_logger
import time
import random
import logging
from collections import defaultdict


URL = "inproc://test123"  # irl we should perhaps generate a random string to use as the inproc url
WORDS = ['Terrific', 'Tremendous', 'Loser', 'Tough', 'Weak', 'Smart', 'Dangerous', 'Stupid', 'Zero', 'Huge', 'Amazing',
         'Rich', 'Winning', 'Bad', 'Moron', 'Classy']
NUM_MSGS = 16
SEND_RATE = 1
REPLY_PROB = 0.75

class MainThread:
    def __init__(self):
        self.log = get_logger("MainThread")
        self.log.debug("Main thread started")
        self.ctx = zmq.asyncio.Context()
        # self.ctx = zmq.Context()

        self.reactor_socket = self.ctx.socket(zmq.PAIR)
        self.reactor_socket.bind(URL)
        self.reactor = None

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.thread = Thread(target=self.run_reactor, args=(self.ctx,))

    def run_reactor(self, context):
        self.log.debug("Running reactor")
        self.reactor = ReactorThread(context)
        self.log.error("Reactor running nonblocking (this should not happen!!!)")

    async def start_sending(self):
        return
        self.log.debug("Starting infinite sending")
        while True:
            msg = random.choice(WORDS).upper()
            self.log.debug("\n\nSending msg: {}".format(msg))
            await self.reactor_socket.send(msg.encode())
            time.sleep(SEND_RATE)

    async def start_receiving(self):
        time.sleep(1.5)
        self.log.info("---  MT starting receiving...  ----")
        while True:
            self.log.critical("Mainthread waiting for msg...")
            msg = await self.reactor_socket.recv()
            self.log.critical("Mainthread got msg: {}".format(msg))
            await self.reactor_socket.send(b'oh hi reactor this is mainthread')

    def go(self):
        self.log.debug("Mainthread GO!")
        self.thread.start()
        self.loop.run_until_complete(self.start_receiving())
        # self.loop.run_in_executor(None, self.start_receiving)

        self.loop.run_until_complete(asyncio.gather(self.start_receiving(), self.start_sending()))

        # self.log.debug("This is not blocking yay")
        # time.sleep(1)
        #
        # # self.start_sending()
        # self.log.info("about to poke reactor from his nap")
        # self.reactor_socket.send(b'are u done with ur nap my guy')

    def send_msg(self):
        msg = random.choice(WORDS).upper()
        self.log.debug("Sending msg: {}".format(msg))
        self.reactor_socket.send(msg.encode())


class ReactorThread:
    def __init__(self, context):
        self.log = get_logger("ReactorThread")
        self.ctx = context

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.main_socket = self.ctx.socket(zmq.PAIR)
        self.main_socket.connect(URL)
        # self.loop = asyncio.get_event_loop()

        self.log.debug("sleeping 1 second...")
        time.sleep(1)
        self.log.debug("sending msg to main thread")
        self.main_socket.send(b'hihihi this is ur good fren the reactor')

        self.loop.run_until_complete(self.start_recv())
        # self.loop.run_until_complete(asyncio.gather(self.start_recv(), self.send_something()))

        # self.start_recv()

    async def start_recv(self):
        await asyncio.sleep(2)
        self.log.debug("-- Reactor starting receiving... --")
        while True:
            self.log.debug("reactor waiting for msg..")
            msg = await self.main_socket.recv()
            self.log.debug("reactor got msg: {}".format(msg))
            self.handle_msg(msg)

    async def send_something(self):
        self.log.debug("send_something sleeping...")
        await asyncio.sleep(1)
        self.log.debug("about to send something to main thread")
        self.main_socket.send(b'ok reactor done with nap')
        self.log.debug("sent msg to mainthread")

        # self.log.debug("send_something sleeping again...")
        # await asyncio.sleep(1)
        # self.log.debug("sending another thing to main thread")
        # self.main_socket.send(b"heres another message for ya")


    def handle_msg(self, msg):
        if random.random() < REPLY_PROB:
            reply = "Thanks for the msg -- {}".format(msg)
            self.log.debug("replying with: {}".format(reply))
            self.main_socket.send(reply.encode())  # TODO -- can this be awaited
        else:
            self.log.debug("Not replying to msg {}".format(msg))


def step1(context=None):
    """Step 1"""
    context = context or zmq.Context.instance()
    # Signal downstream to step 2
    sender = context.socket(zmq.PAIR)
    sender.connect("inproc://step2")

    sender.send(b"")

def step2(context=None):
    """Step 2"""
    context = context or zmq.Context.instance()
    # Bind to inproc: endpoint, then start upstream thread
    receiver = context.socket(zmq.PAIR)
    receiver.bind("inproc://step2")

    thread = Thread(target=step1)
    thread.start()

    # Wait for signal
    msg = receiver.recv()

    # Signal downstream to step 3
    sender = context.socket(zmq.PAIR)
    sender.connect("inproc://step3")
    sender.send(b"")

def main():
    """ server routine """
    # Prepare our context and sockets
    context = zmq.Context.instance()

    # Bind to inproc: endpoint, then start upstream thread
    receiver = context.socket(zmq.PAIR)
    receiver.bind("inproc://step3")

    thread = Thread(target=step2)
    thread.start()

    # Wait for signal
    string = receiver.recv()

    print("Test successful!")

    receiver.close()
    context.term()

if __name__ == "__main__":
    mt = MainThread()
    mt.go()

    time.sleep(SEND_RATE)

    for x in range(NUM_MSGS):
        print("Sending msg #{}".format(x))
        mt.send_msg()
        time.sleep(SEND_RATE)