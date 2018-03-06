from zmq.asyncio import Context
from cilantro import Constants
import zmq
import multiprocessing
from multiprocessing import Process, Array
import asyncio

base_url = Constants.BaseNode.BaseUrl
subscriber_port = Constants.BaseNode.SubscriberPort
publisher_port = Constants.BaseNode.PublisherPort

subscriber_url = 'tcp://{}:{}'.format(base_url, subscriber_port)
publisher_url = 'tcp://{}:{}'.format(base_url, publisher_port)

def recieve_messages():
    context = Context.instance()

    sub_socket = context.socket(socket_type=zmq.SUB)

    pub_socket = context.socket(socket_type=zmq.PUB)
    pub_socket.connect(publisher_url)

    sub_socket.bind(subscriber_url)
    sub_socket.setsockopt(zmq.SUBSCRIBE, b'')

    loop = asyncio.new_event_loop()
    loop.run_until_complete(asyncio.wait(loop(sub_socket.recv_multipart)))


async def loop(recieve):
    while True:
        msg = recieve()
        print(msg)

p = Process(target=recieve_messages())
p.start()

import time
time.sleep(1)

p.terminate()