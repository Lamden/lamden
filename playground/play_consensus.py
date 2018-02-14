import os
import random
import threading
import time
import zmq.green as zmq


context = zmq.Context()

pub = context.socket(zmq.PUB)
sub = context.socket(zmq.SUB)
sub.setsockopt(zmq.SUBSCRIBE, b'')

pub.connect('tcp://127.0.0.1:5000')
sub.connect('tcp://127.0.0.1:5000')


def publish():
    for i in range(10000):
        pub.send(b'b')


def subscribe():
    for i in range(10000):
        msg = sub.recv()
        print(msg)


p = threading.Thread(target=publish())
s = threading.Thread(target=subscribe())

p.start()
s.start()