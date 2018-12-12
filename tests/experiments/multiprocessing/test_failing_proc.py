from time import sleep
from multiprocessing import Process


def do_that():
    while True:
        print("that")
        sleep(1)


if __name__ == '__main__':
    p = Process(target=do_that)
    p.start()
