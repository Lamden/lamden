from multiprocessing import Process
from cilantro_ee.core.logger.base import get_logger
import asyncio, zmq.asyncio, zmq
from cilantro_ee.core.sockets.lsocket import *
from cilantro_ee.core.sockets.socket_manager import *
from cilantro_ee.core.utils.worker import *
from cilantro_ee.messages.signals.poke import *

FILTER = 'HI'
IP = '127.0.0.1'
PORT = 9002


def start_pub():
    log = get_logger("PUB")
    worker = Worker('A'*64, name='pub')

    pub = worker.manager.create_socket(zmq.PUB)
    pub.bind(port=PORT, ip=IP)

    log.important("starting pub")

    async def start():
        while True:
            poke = Poke.create()
            log.info("sending poke {}".format(poke))
            pub.send_msg(poke, header=FILTER.encode())
            await asyncio.sleep(1)

    worker.tasks.append(start())
    worker.loop.run_until_complete(asyncio.gather(*worker.tasks))


def start_sub():
    log = get_logger("Sub")
    worker = Worker('A'*64, name='sub')

    sub = worker.manager.create_socket(zmq.SUB)

    async def _delayed_connect():
        log.debug("waiting before connecting....")
        await asyncio.sleep(1)
        log.debug("about to connect!")
        sub.setsockopt(zmq.SUBSCRIBE, FILTER.encode())
        sub.connect(port=PORT, ip=IP)

    def handle_msg(frames):
        log.critical("yayyyy got frames {}".format(frames))

    t = sub.add_handler(handle_msg)
    worker.tasks.append(t)
    worker.tasks.append(_delayed_connect())
    worker.loop.run_until_complete(asyncio.gather(*worker.tasks))


if __name__ == '__main__':
    p1 = Process(target=start_pub)
    p2 = Process(target=start_sub)

    for p in (p1, p2):
        p.start()

    for p in (p1, p2):
        p.join()




