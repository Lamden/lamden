import sys
import time
from multiprocessing import Process, Queue

NUM_MSGS = 10000000

def worker(q):
    for task_nbr in range(NUM_MSGS):
        message = q.get()
    sys.exit(1)


def main():
    send_q = Queue()
    Process(target=worker, args=(send_q,)).start()
    for num in range(NUM_MSGS):
        send_q.put("MESSAGE")


if __name__ == "__main__":
    print("Starting Queue Test...")
    start_time = time.time()
    main()
    end_time = time.time()
    duration = end_time - start_time
    msg_per_sec = NUM_MSGS / duration

    print("Duration: %s" % duration)
    print("Messages Per Second: %s" % msg_per_sec)