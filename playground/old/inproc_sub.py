import sys
import zmq

INPROC_URL = "inproc://hello"

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.setsockopt(zmq.SUBSCRIBE, b'')

socket.connect(INPROC_URL)

while True:
    print("Sub waiting for msg...")
    msg = socket.recv()
    print("Sub received msg: {}".format(msg))