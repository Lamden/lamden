import zmq.asyncio
import asyncio
from cilantro.logger.base import get_logger
from multiprocessing import Process
import time


PORT = 1234
IP = '127.0.0.1'
PROTOCOL = 'tcp'

URL = "{}://{}:{}".format(PROTOCOL, IP, PORT)


def start_pub():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx = zmq.asyncio.Context()

    log = get_logger("Pub")

    pub = ctx.socket(zmq.PUB)
    pub.bind(URL)

    log.important3("Starting publishing")

    for i in range(1000):
        log.info("pub sending msg {}".format(i))
        pub.send_multipart([b'', str(i).encode()])
        time.sleep(1)

    # async def _pub():
    #     for i in range(1000):
    #         log.info("pub sending msg {}".format(i))
    #         pub.send_multipart([b'', str(i).encode()])
    #         time.sleep(1)

    # loop.run_until_complete(_pub())


def start_sub():
    def handler_func(frames):
        log.important("handler func got frames: {}".format(frames))

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

    log = get_logger("Sub")

    sub = ctx.socket(zmq.SUB)

    # log.important3("taking dat nap")
    # time.sleep(4)
    # log.important3("done wit dat nap")

    def connect_sub(sub_socket):
        log.important2("CONNECTING SUB SOCKET")
        sub_socket.connect(URL)
        sub_socket.setsockopt(zmq.SUBSCRIBE, b'')

    # sub.connect(URL)
    # sub.setsockopt(zmq.SUBSCRIBE, b'')
    loop.call_later(5, connect_sub, sub)

    # log.important3("taking dat nap")
    # time.sleep(4)
    # log.important3("done wit dat nap")

    log.important3("Starting loop")
    loop.run_until_complete(listen(sub, handler_func))


if __name__ == '__main__':
    pub = Process(target=start_pub)
    sub = Process(target=start_sub)

    for p in (pub, sub):
        p.start()
