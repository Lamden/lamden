import zmq

HOST = '127.0.0.1'
PORT = '4444'
URL = 'tcp://{}:{}'.format(HOST, PORT)

context = zmq.Context()
subscriber = context.socket(zmq.SUB)
subscriber.connect(URL)

