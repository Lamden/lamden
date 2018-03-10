import zmq

context = zmq.Context()

reply = context.socket(zmq.REP)
reply.bind('tcp://*:7770')

request = context.socket(zmq.REQ)
request.connect('tcp://127.0.0.1:7770')

request.send(b'howdy')

print(reply.recv())

reply.send(b'hello')

print(request.recv())