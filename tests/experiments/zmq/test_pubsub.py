import zmq, time
from cilantro_ee.logger.base import get_logger
from multiprocessing import Process


def start_sub(url):
    log = get_logger("SUB")
    ctx = zmq.Context()
    sock = ctx.socket(zmq.SUB)
    sock.setsockopt(zmq.SUBSCRIBE, b'')

    log.important('conn')
    sock.bind(url)
    sock.bind(url)
    sock.bind(url)
    sock.bind(url)

    log.important('slep')
    time.sleep(1)

    while True:
        log.spam('wait for msg')
        msg = sock.recv_multipart()
        log.important('got msg {}'.format(msg))


def start_pub(url):
    log = get_logger("SUB")
    ctx = zmq.Context()
    sock = ctx.socket(zmq.PUB)

    log.important2('bind')
    sock.connect(url)
    sock.connect(url)
    sock.connect(url)

    count = 0
    while True:
        log.important2('send {}'.format(count))
        sock.send_multipart([b'', "hi {}".format(count).encode()])
        count += 1
        time.sleep(0.25)


if __name__ == '__main__':
    URL = 'tcp://127.0.0.1:9865'
    p1 = Process(target=start_sub, args=(URL,))
    p2 = Process(target=start_pub, args=(URL,))

    p1.start()
    p2.start()
    p1.join()
