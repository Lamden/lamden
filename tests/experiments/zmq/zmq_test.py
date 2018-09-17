import zmq.asyncio
import asyncio
from cilantro.logger.base import get_logger
from multiprocessing import Process
import time


PORT = 1234
IP = '127.0.0.1'
PROTOCOL = 'tcp'

URL = "{}://{}:{}".format(PROTOCOL, IP, PORT)

SUB_URL = "{}://{}:{}".format(PROTOCOL, IP, 9090)
SUB2_URL = "{}://{}:{}".format(PROTOCOL, IP, 9091)


def start_pub(urls, name):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx = zmq.asyncio.Context()

    log = get_logger(name)

    pub = ctx.socket(zmq.PUB)
    for url in urls:
        log.socket("pub connecting to url {}".format(url))
        pub.connect(url)

    log.important3("Starting publishing")

    for i in range(1000):
        log.info("pub sending msg {} FROM PUB {}".format(i, name))
        pub.send_multipart([b'', str('from ' + name + ' ' + str(i)).encode()])
        time.sleep(1)

    # async def _pub():
    #     for i in range(1000):
    #         log.info("pub sending msg {}".format(i))
    #         pub.send_multipart([b'', str(i).encode()])
    #         time.sleep(1)

    # loop.run_until_complete(_pub())


def start_sub(url, name):
    def handler_func(frames):
        log.important("[{}] handler func got frames: {}".format(name, frames))

    async def listen(socket, handler_func):
        # log.important3("taking dat nap")
        # time.sleep(4)
        # log.important3("done wit dat nap")

        log.socket("Starting listener on socket {}".format(socket))
        while True:
            try:
                log.socket("Socket {} awaiting a msg...".format(socket))
                msg = await socket.recv_multipart()
            except Exception as e:
                if type(e) is asyncio.CancelledError:
                    log.important("Socket got asyncio.CancelledError. Breaking from lister loop.")  # TODO change log level on this
                    break
                else:
                    log.critical("Socket got exception! Exception:\n{}".format(e))
                    raise e

            log.spam("Socket recv multipart msg:\n{}".format(msg))
            handler_func(msg)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx = zmq.asyncio.Context()

    log = get_logger(name)

    sub = ctx.socket(zmq.SUB)

    # log.important3("taking dat nap")
    # time.sleep(4)
    # log.important3("done wit dat nap")

    sub.bind(url)
    sub.setsockopt(zmq.SUBSCRIBE, b'')

    # log.important3("taking dat nap")
    # time.sleep(4)
    # log.important3("done wit dat nap")

    log.important3("Starting loop")
    loop.run_until_complete(listen(sub, handler_func))


if __name__ == '__main__':
    pub = Process(target=start_pub, args=([SUB_URL, SUB2_URL], 'PUB 1'))
    pub2 = Process(target=start_pub, args=([SUB_URL, SUB2_URL], 'PUB 2'))
    # pub2 = Process(target=start_pub, args=([URL],))

    sub = Process(target=start_sub, args=(SUB_URL, 'SUB 1'))
    sub2 = Process(target=start_sub, args=(SUB2_URL, 'SUB 2'))

    for p in (pub, pub2, sub2, sub):
        p.start()
