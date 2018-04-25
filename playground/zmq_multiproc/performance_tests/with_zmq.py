import sys
import zmq
from multiprocessing import Process
import time
from cilantro.logger import get_logger
import threading


PUSH_PULL, SUB_PUB, PAIR, DEAL_ROUTE, REQ_REPLY = range(5)

# SET TEST VARS HERE
PATTERN = PAIR
# NUM_MSGS = 10000000
NUM_MSGS = 10


CONFIG = {PUSH_PULL: {'url': "tcp://127.0.0.1:5557", 'binder': zmq.PUSH, 'connector': zmq.PULL},
          PAIR: {'url': "inproc://test-letsgo", 'binder': zmq.PAIR, 'connector': zmq.PAIR}}
URL = CONFIG[PATTERN]['url']
BINDER = CONFIG[PATTERN]['binder']
CONNECTOR = CONFIG[PATTERN]['connector']

def worker(context=None):
    # print("worker started")
    if not context:
        print("Worker creating fresh context")
        context = zmq.Context.instance()
        # context = zmq.Context()

    work_receiver = context.socket(CONNECTOR)
    # work_receiver.bind(URL)
    work_receiver.connect(URL)

    # time.sleep(0.25)
    # print("worker signaling main...")
    # work_receiver.send(b'im rdy')
    # print("worker signaled main thread")

    for task_nbr in range(NUM_MSGS):
        # print("** working waiting for msg #{}".format(task_nbr))
        msg = work_receiver.recv_pyobj()
        print("got msg: {}".format(msg))
        # print("**** working got msg #{} : {}".format(task_nbr, msg))

    sys.exit(1)


def main():
    # print("main starting")
    # context = zmq.Context.instance()
    context = zmq.Context()

    ventilator_send = context.socket(BINDER)
    # ventilator_send.connect(URL)
    ventilator_send.bind(URL)

    # print("main starting child thread")
    # Process(target=worker, args=()).start()
    t = threading.Thread(target=worker, args=(context,))
    t.start()

    # print("--- main waiting for child thread...")
    # msg = ventilator_send.recv()
    # print("!!! main got rdy msg: {}".format(msg))

    for num in range(NUM_MSGS):
        # print("main about to send msg...")
        # ventilator_send.send("hi {}".format(num).encode())

        # ventilator_send.send(b"MESSAGE")

        ventilator_send.send_pyobj(('val1', {'hello': 'hi'}))

        # print("main sent msg #{}".format(num))
        # print("hey i send a message")


if __name__ == "__main__":
    log = get_logger("Main")
    log.info("Starting ZMQ Test...")
    start_time = time.time()
    main()
    end_time = time.time()
    duration = end_time - start_time
    msg_per_sec = NUM_MSGS / duration

    log.info("Duration: %s" % duration)
    log.info("Messages Per Second: %s" % msg_per_sec)
