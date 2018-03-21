# import threading
# import zmq
#
#
# def config_router_dealer(context=None):
#     context = context or zmq.Context.instance()
#     sender = context.socket(zmq.DEALER)
#     receiver = context.socket(zmq.ROU)
#
#
# def step1(context=None):
#     """Step 1"""
#     print("doing step ONE with context ", context)
#     context = context or zmq.Context.instance()
#     # Signal downstream to step 2
#     sender = context.socket(zmq.PAIR)
#     sender.connect("inproc://step2")
#
#     sender.send(b"")
#
# def step2(context=None):
#     """Step 2"""
#     print("doing step TWO with context ", context)
#     context = context or zmq.Context.instance()
#     # Bind to inproc: endpoint, then start upstream thread
#     receiver = context.socket(zmq.PAIR)
#     print("step 2 binding to inproc://step2")
#     receiver.bind("inproc://step2")
#
#     thread = threading.Thread(target=step1)
#     thread.start()
#
#     # Wait for signal
#     print("step 2 waiting for sig")
#     msg = receiver.recv()
#
#     # Signal downstream to step 3
#     sender = context.socket(zmq.PAIR)
#     print("step2 connecting to inproc://step3")
#     sender.connect("inproc://step3")
#     sender.send(b"")
#
# def main():
#     """ server routine """
#     # Prepare our context and sockets
#     context = zmq.Context.instance()
#
#     # Bind to inproc: endpoint, then start upstream thread
#     receiver = context.socket(zmq.PAIR)
#     receiver.bind("inproc://step3")
#
#     thread = threading.Thread(target=step2)
#     thread.start()
#
#     # Wait for signal
#     print("main waiting for step3")
#     string = receiver.recv()
#
#     print("Test successful!")
#
#     receiver.close()
#     context.term()
#
# if __name__ == "__main__":
#     main()


import time
import random
from threading import Thread

import zmq

# We have two workers, here we copy the code, normally these would
# run on different boxes…
#
def worker_a(context=None):
    context = context or zmq.Context.instance()
    worker = context.socket(zmq.DEALER)
    worker.setsockopt(zmq.IDENTITY, b'A')
    worker.connect("ipc://routing.ipc")

    total = 0
    while True:
        # We receive one part, with the workload
        request = worker.recv()
        finished = request == b"END"
        if finished:
            print("A received: %s" % total)
            break
        total += 1

def worker_b(context=None):
    context = context or zmq.Context.instance()
    worker = context.socket(zmq.DEALER)
    worker.setsockopt(zmq.IDENTITY, b'B')
    worker.connect("ipc://routing.ipc")

    total = 0
    while True:
        # We receive one part, with the workload
        request = worker.recv()
        finished = request == b"END"
        if finished:
            print("B received: %s" % total)
            break
        total += 1

context = zmq.Context.instance()
client = context.socket(zmq.ROUTER)
client.bind("ipc://routing.ipc")

Thread(target=worker_a).start()
Thread(target=worker_b).start()

# Wait for threads to stabilize
time.sleep(1)

# Send 10 tasks scattered to A twice as often as B
for _ in range(10):
    # Send two message parts, first the address…
    ident = random.choice([b'A', b'A', b'B'])
    # And then the workload
    work = b"This is the workload"
    client.send_multipart([ident, work])

client.send_multipart([b'A', b'END'])
client.send_multipart([b'B', b'END'])