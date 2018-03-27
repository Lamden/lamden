import time
import zmq

# INPROC_URL = "ipc://hello"
INPROC_URL = "tcp://127.0.0.1:5555"

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind(INPROC_URL)

while True:
    msg = "yo"
    print("sending msg: {}".format(msg))
    socket.send(msg.encode())
    time.sleep(1)