import zmq, time
from cilantro.logger.base import get_logger
from multiprocessing import Process


def start_sender(url):
    log = get_logger("SUB")
    ctx = zmq.Context()
    sock = ctx.socket(zmq.ROUTER)
    sock.setsockopt(zmq.IDENTITY, b'sender')

    log.important('conn')
    sock.connect(url)

    count = 0
    while True:
        log.important2('send {}'.format(count))
        sock.send_multipart([b'recvr', "hi {}".format(count).encode()])
        sock.send_multipart([b'i_dont_exist', "hi {}".format(count).encode()])
        count += 1
        time.sleep(0.25)


def start_recvr(url):
    log = get_logger("SUB")
    ctx = zmq.Context()
    sock = ctx.socket(zmq.ROUTER)
    sock.setsockopt(zmq.IDENTITY, b'recvr')

    log.important2('bind')
    sock.bind(url)

    log.important('slep')
    time.sleep(1)

    for _ in range(10):
        log.spam('wait for msg')
        msg = sock.recv_multipart()
        log.important('got msg {}'.format(msg))

    log.important3("WE OUT THIS")
    sock.close()


if __name__ == '__main__':
    URL = 'tcp://127.0.0.1:9865'
    p1 = Process(target=start_sender, args=(URL,))
    p2 = Process(target=start_recvr, args=(URL,))

    p1.start()
    p2.start()
    # p1.join()

    time.sleep(10)
    p3 = Process(target=start_recvr, args=(URL,))
    p3.start()
    p3.join()
