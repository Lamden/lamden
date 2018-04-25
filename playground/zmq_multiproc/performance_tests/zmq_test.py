import sys
import zmq
from multiprocessing import Process
import time

NUM_MSGS = 10000000
# NUM_MSGS = 10

def worker():
    context = zmq.Context()
    work_receiver = context.socket(zmq.PULL)
    work_receiver.connect("tcp://127.0.0.1:5557")

    for task_nbr in range(NUM_MSGS):
        message = work_receiver.recv()

    sys.exit(1)


def main():
    Process(target=worker, args=()).start()
    context = zmq.Context()
    ventilator_send = context.socket(zmq.PUSH)
    ventilator_send.bind("tcp://127.0.0.1:5557")
    for num in range(NUM_MSGS):
        ventilator_send.send(b"MESSAGE")


if __name__ == "__main__":
    print("Starting ZMQ Test...")
    start_time = time.time()
    main()
    end_time = time.time()
    duration = end_time - start_time
    msg_per_sec = NUM_MSGS / duration

    print("Duration: %s" % duration)
    print("Messages Per Second: %s" % msg_per_sec)