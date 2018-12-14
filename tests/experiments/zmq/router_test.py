import zmq, zmq.asyncio, asyncio
from cilantro.logger import get_logger
import time
from multiprocessing import Process

URL1 = "tcp://127.0.0.1:9001"
URL2 = "tcp://127.0.0.1:9002"


def build_router(identity: bytes):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(socket_type=zmq.ROUTER)
    sock.setsockopt(zmq.IDENTITY, identity)
    return sock, ctx, loop


def start_sender(identity, url, recv_id):
    log = get_logger("Sender[{}]".format(identity.decode()))
    sock, ctx, loop = build_router(identity=identity)
    log.debug("BINDing to url {}".format(url))
    sock.bind(url)

    async def run():
        log.spam('sender waiting to start...')
        await asyncio.sleep(0.25)
        log.spam('sender done waiting')
        await asyncio.sleep(0.25)
        count = 0
        while True:
            log.debug("sending msg using id frame {}..".format(recv_id.decode()))
            sock.send_multipart([recv_id, recv_id + b'  -  ' + ' #{} hi its me sender -- '
                                .format(count).encode() + identity])
            count += 1
            await asyncio.sleep(1)

    loop.run_until_complete(run())


def start_receiver(identity, homies):
    log = get_logger("Receiver")
    sock, ctx, loop = build_router(identity=identity)

    async def connect():
        for homie in homies:
            log.socket("connecting to a homie at url {}".format(homie))
            sock.connect(homie)
            log.debug("slep")
            await asyncio.sleep(1)
            log.debug('done slep')

    async def listen():
        await asyncio.sleep(0.1)
        while True:
            log.info("Waiting for msg...")
            msg = await sock.recv_multipart()
            log.notice("GOT MSG {}!".format(msg))

    loop.run_until_complete(asyncio.gather(connect(), listen()))


if __name__ == '__main__':
    sender_1 = Process(target=start_sender, args=(b'1', URL1, b'3'))
    sender_2 = Process(target=start_sender, args=(b'2', URL2, b'3'))
    receiver = Process(target=start_receiver, args=(b'3', [URL1, URL2]))

    for p in (sender_1, sender_2, receiver):
        p.start()
