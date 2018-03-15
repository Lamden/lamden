from zmq.asyncio import Context
from cilantro import Constants
import zmq
import multiprocessing
from multiprocessing import Process, Array
import asyncio
import time

# base_url = Constants.BaseNode.BaseUrl
# subscriber_port = Constants.BaseNode.SubscriberPort
# publisher_port = Constants.BaseNode.PublisherPort
#
# subscriber_url = 'tcp://{}:{}'.format(base_url, subscriber_port)
# publisher_url = 'tcp://{}:{}'.format(base_url, publisher_port)
#
# def recieve_messages():
#     context = Context.instance()
#
#     sub_socket = context.socket(socket_type=zmq.SUB)
#
#     pub_socket = context.socket(socket_type=zmq.PUB)
#     pub_socket.connect(publisher_url)
#
#     sub_socket.bind(subscriber_url)
#     sub_socket.setsockopt(zmq.SUBSCRIBE, b'')
#
#     loop = asyncio.new_event_loop()
#     loop.run_until_complete(asyncio.wait(loop(sub_socket.recv_multipart)))
#
#
# async def loop(recieve):
#     while True:
#         msg = recieve()
#         print(msg)
#
# p = Process(target=recieve_messages())
# p.start()
#
# import time
# time.sleep(1)
#
# p.terminate()

#
# loop = asyncio.new_event_loop()
# asyncio.set_event_loop(loop)
# context = zmq.Context()

from cilantro.logger import get_logger

# TODO -- why is this not getting fired async?
async def do_task(future, num):
    # request_socket = context.socket(socket_type=zmq.REQ)
    # request_socket.connect(connection)

    # self.log.debug("Poking url: {}".format(connection))

    # poke = Poke.create()
    # poke_msg = Message.create(Poke, poke.serialize())

    # request_socket.send(poke_msg.serialize())
    # msg = await request_socket.recv()

    # self.log.debug("Got request from the poked delegate: {}".format(msg))

    # future.set_result(msg)
    # request_socket.disconnect(connection)
    log = get_logger("Task #{}".format(num))
    log.info("doing work")
    # asyncio.sleep(1)

    while True: asyncio.sleep(1)



# def verify_signature(future):
#     # self.handle_message(future.result())
#     result = future.result()
#     print("got result ", result)
#
#
# NUMS = [0,1,2,3,4]
#
# futures = [asyncio.Future() for _ in range(len(NUMS))]
#
# [f.add_done_callback(verify_signature) for f in futures]
#
# tasks = [do_task(*a) for a in zip(futures, NUMS)]
#
# print("# of tasks: {}".format(len(tasks)))
#
# loop.run_until_complete(asyncio.wait(tasks))
# loop.close()

log = get_logger("Main")

def get_response(connection, num):
    log = get_logger("Task #{}".format(num))
    log.info("Task {} doing work".format(num))
    while True: asyncio.sleep(1)

async def l(ii):
    sub_loop = asyncio.get_event_loop()
    tasks = [sub_loop.run_in_executor(None, get_response, 'abc', i) for i in range(ii)]
    await asyncio.wait(tasks)

NUM_TASKS = 5

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
# loop = asyncio.get_event_loop()

sub_loop = asyncio.get_event_loop()
tasks = [sub_loop.run_in_executor(None, get_response, 'abc', i) for i in range(NUM_TASKS)]

# loop.run_until_complete(l(NUM_TASKS))

log.debug("starting loop")
loop.run_until_complete(asyncio.wait(tasks))
log.debug("done with loop")
