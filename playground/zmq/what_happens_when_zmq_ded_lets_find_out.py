import zmq.asyncio
import zmq
import asyncio
import time
import random
from cilantro.logger.base import get_logger
from multiprocessing import Process
import funcools

URL =  "tcp://127.0.0.1:8899"
URL2 =  "tcp://127.0.0.1:8869"
MSG = b'hi'
KILL_SIG = b'die'


def spam():
    log = get_logger("PUB GUY")
    ctx = zmq.Context()
    pub = ctx.socket(socket_type=zmq.PUB)
    pair = ctx.socket(socket_type=zmq.PAIR)

    pub.bind(URL)
    pair.bind(URL2)

    log.important("PUB about to start pumping messages at url {}".format(URL))
    # while True:
    for i in range(4):
        log.spam("PUB sending msg {}".format(MSG))
        pub.send(str(i).encode())
        time.sleep(1)

    log.important("PUB sending kill sig")
    pair.send(KILL_SIG)


def listen():
    async def sub_listen(s):
        log.socket("Starting listening on PUB socket {}".format(s))
        while True:
            log.spam("waiting for msg on sock {}".format(s))
            msg = await s.recv()
            log.notice("sock {} got msg {}".format(s, msg))


    async def pair_listen(pair_sock, sub_sock, sub_fut):
        log.socket("Starting listening on PAIR socket {}".format(pair_sock))
        while True:
            log.info("waiting for pair message...")
            msg = await pair_sock.recv()
            log.info("GOT PAIR MSG {}".format(msg))
            assert msg == KILL_SIG, "Can only get kill sig from pair socket"

            # Teardown sub
            log.important3("CANCELING SUB FUTURE")
            sub_fut.cancel()
            log.important3("CLOSING SUB SOCKET")
            sub_sock.close()

            log.important3("stopping dat loop")
            loop = asyncio.get_event_loop()
            loop.stop()

            break

    log = get_logger("SUB{}".format(random.randint(0, 256)))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx = zmq.asyncio.Context()

    sub = ctx.socket(socket_type=zmq.SUB)
    pair = ctx.socket(socket_type=zmq.PAIR)
    sub.setsockopt(zmq.SUBSCRIBE, b'')
    sub.connect(URL)
    pair.connect(URL2)

    def cleanup(fut, sub_fut, sub_sock, pair_sock, pair_fut):

    log.important2("SUB starting to listen to messages at URL {}".format(URL))


    sub_fut = asyncio.ensure_future(sub_listen(sub))
    pair_fut = asyncio.ensure_future(pair_listen(pair_sock=pair, sub_sock=sub, sub_fut=sub_fut))
    # loop.run_until_complete(sub_listen(sub, fut))

    loop.run_forever()

    # Cleanup
    sub.close()
    loop.close()


def main():
    pub = Process(target=spam)
    sub = Process(target=listen)

    for p in (pub, sub):
        p.start()


if __name__ == '__main__':
    main()