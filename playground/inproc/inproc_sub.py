import sys
import zmq
from multiprocessing import Process

# INPROC_URL = "ipc://hello"
INPROC_URL = "tcp://127.0.0.1:5555"

def start_sub(name):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE, b'')

    socket.connect(INPROC_URL)
    while True:
        print("{} waiting for msg...".format(name))
        msg = socket.recv()
        print("{} received msg: {}".format(name, msg))

# context = zmq.Context()
# socket = context.socket(zmq.SUB)
# socket.setsockopt(zmq.SUBSCRIBE, b'')
#
# socket.connect(INPROC_URL)
#
#
# context2 = zmq.Context()
# socket2 = context2.socket(zmq.SUB)
# socket2.setsockopt(zmq.SUBSCRIBE, b'')
#
# socket2.connect(INPROC_URL)

p1 = Process(target=start_sub, args=("Socket1",))
p2 = Process(target=start_sub, args=("Socket2",))

p1.start()
p2.start()


# while True:
#     print("{} waiting for msg...".format("S1"))
#     msg = socket.recv()
#     print("{} received msg: {}".format("S1", msg))