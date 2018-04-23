import zmq
import time
from cilantro.logger import get_logger

log = get_logger("Sender")
URL = "tcp://127.0.0.1:8844"
MSG = b"AY ITS YA BOY COMIN AT U LIKE OVER DAT ZMQ TCP!!!"

ctx = zmq.Context()
sock = ctx.socket(socket_type=zmq.DEAL)
sock.identity = id.encode('ascii')

while True:
    log.debug("sending msg")
    sock.send(MSG)