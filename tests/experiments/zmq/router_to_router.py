import zmq
from cilantro.logger import get_logger
import time
from multiprocessing import Process

URL1 = "tcp://127.0.0.1:9001"
URL2 = "tcp://127.0.0.1:9002"


def build_router(identity: bytes):
    ctx = zmq.Context()
    sock = ctx.socket(socket_type=zmq.ROUTER)
    sock.setsockopt(zmq.IDENTITY, identity)
    return sock

def start_sender(identity, url, recv_id):
    log = get_logger("Sender[{}]".format(identity.decode()))
    sock = build_router(identity=identity)
    log.debug("BINDing to url {}".format(url))
    sock.bind(url)

    while True:
        log.debug("sending msg using id frame {}..".format(recv_id.decode()))
        sock.send_multipart([recv_id, recv_id + b'  -  ' + b'hi its me sender -- ' + identity])
        time.sleep(2)


def start_receiver(identity, homies):
    log = get_logger("Receiver")
    sock = build_router(identity=identity)

    # connect to the homies
    for homie in homies:
        log.info("connecting to a homie at url {}".format(homie))
        sock.connect(homie)

    while True:
        log.info("Waiting for msg...")
        msg = sock.recv_multipart()
        log.notice("GOT MSG {}!".format(msg))


if __name__ == '__main__':
    sender_1 = Process(target=start_sender, args=(b'1', URL1, b'3'))
    sender_2 = Process(target=start_sender, args=(b'2', URL2, b'3'))
    receiver = Process(target=start_receiver, args=(b'3', [URL1, URL2]))

    for p in (sender_1, sender_2, receiver):
        p.start()
