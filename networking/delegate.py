import sys
import time
import zmq
from transactions import basic_transaction as transaction
from serialization import basic_serialization
import datetime


def puller():
	print('delegate listening...')
	context = zmq.Context()

	# Socket to receive messages on
	witness = context.socket(zmq.PULL)
	witness.bind("tcp://*:5559")

	while True:
		s = witness.recv()
		print(s)

if __name__ == "__main__":
	puller()