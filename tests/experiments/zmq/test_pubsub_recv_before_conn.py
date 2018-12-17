import zmq, time, asyncio, zmq.asyncio
from cilantro.logger.base import get_logger
from multiprocessing import Process


def start_sub(url):
    log = get_logger("SUB")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.SUB)
    sock.setsockopt(zmq.SUBSCRIBE, b'')

    async def recv():
        while True:
            log.spam('wait for msg')
            msg = await sock.recv_multipart()
            log.important('got msg {}'.format(msg))

    async def conn():
        log.critical("sleeping before conn")
        await asyncio.sleep(1)
        sock.connect(url)
        log.critical("connected")

    loop.run_until_complete(asyncio.gather(recv(), conn()))


def start_pub(url):
    log = get_logger("SUB")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.PUB)

    log.important2('bind')
    sock.bind(url)

    async def send():
        count = 0
        while True:
            log.important2('send {}'.format(count))
            sock.send_multipart([b'', "hi {}".format(count).encode()])
            count += 1
            time.sleep(0.25)

    loop.run_until_complete(asyncio.gather(send(),))


if __name__ == '__main__':
    URL = 'tcp://127.0.0.1:9865'
    p1 = Process(target=start_sub, args=(URL,))
    p2 = Process(target=start_pub, args=(URL,))

    p1.start()
    p2.start()
    p1.join()
