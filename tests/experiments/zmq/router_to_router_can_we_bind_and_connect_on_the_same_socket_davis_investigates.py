import zmq.asyncio
import asyncio
from cilantro_ee.logger import get_logger
import time
from multiprocessing import Process
import random


URL1 = "tcp://127.0.0.1:9001"
URL2 = "tcp://127.0.0.1:9002"
URL3 = "tcp://127.0.0.1:9003"


async def listen(sock, log):
    log.socket("Starting listening...")
    while True:
        log.info("Waiting for msg...")
        msg = await sock.recv_multipart()
        log.notice("GOT MSG {}!".format(msg))


async def talk(sock, log, msg, receiver_ids):
    log.socket("bout to start talking with msg {}".format(msg.decode()))
    while True:
        sleep = random.randint(0, 4)
        log.debug("sleeping for {} seconds before sending message".format(sleep))
        await asyncio.sleep(sleep)
        for id in receiver_ids:  # TODO take a random sample from receiver_ids?
            log.debugv("sending to id {}".format(id.decode()))
            sock.send_multipart([id, msg])


def build_comm(identity: bytes):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(socket_type=zmq.ROUTER)
    sock.setsockopt(zmq.IDENTITY, identity)
    return loop, ctx, sock


def start_node(identity, url, homie_urls, homie_ids):
    log = get_logger("Node[{}]".format(identity.decode()))
    loop, ctx, sock = build_comm(identity=identity)
    log.debug("BINDing to url {}".format(url))
    msg = b'hi its me -- ' + identity
    sock.bind(url)

    for url in homie_urls:
        log.debug("CONNECTing to url {}".format(url))
        sock.connect(url)

    loop.run_until_complete(asyncio.gather(listen(sock, log), talk(sock, log, msg, homie_ids)))


if __name__ == '__main__':
    sender_1 = Process(target=start_node, args=(b'1', URL1, [URL2, URL3], [b'2', b'3']))
    sender_2 = Process(target=start_node, args=(b'2', URL2, [URL1, URL3], [b'1', b'3']))
    receiver = Process(target=start_node, args=(b'3', URL3, [URL1, URL2], [b'1', b'2']))

    for p in (sender_1, sender_2, receiver):
        p.start()

