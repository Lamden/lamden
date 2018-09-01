import zmq
import time
from cilantro.logger import get_logger


URL = "ipc://localhost:9912"
NUM_MSG = 10
NUM_PULLERS = 2
SLEEP_TIME = 1


def run_pusher():
    log = get_logger("Pusher")
    log.notice("Starting pusher...")
    ctx = zmq.Context()

    sock = ctx.socket(socket_type=zmq.PUSH)

    for _ in range(NUM_MSG):
        sock.send(b'sup')


def run_puller(num):
    log = get_logger("Pusher[{}]".format(num))
    log.notice("Starting puller...")
    ctx = zmq.Context()

    sock = ctx.socket(socket_type=zmq.PULL)
