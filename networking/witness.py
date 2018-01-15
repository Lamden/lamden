import sys
import time
import zmq
from transactions import basic_transaction as transaction
from serialization import basic_serialization
import datetime

# asynchronize eventually
def main():
	context = zmq.Context()

	receiver = context.socket(zmq.REP)
	receiver.bind("tcp://*:5555")

	while True:
		s = receiver.recv()
		tx = basic_serialization.deserialize(s)

		if (transaction.check_proof(tx['payload'], tx['metadata']['proof'])) == True:
			receiver.send_string('success')
		else:
			receiver.send_string('failure')
		print(s)

def puller():
	print('witness listening...')
	context = zmq.Context()

	# Socket to receive messages on
	public = context.socket(zmq.PULL)
	public.bind("tcp://*:5558")

	delegates = context.socket(zmq.PUSH)
	delegates.connect("tcp://localhost:5559")

	while True:
		s = public.recv()

		try:
			tx = basic_serialization.deserialize(s)

			if (transaction.check_proof(tx['payload'], tx['metadata']['proof'])) == True:
				print(s)
				delegates.send(s)
			else:
				print('failure')

		except:
			pass

if __name__ == "__main__":
	puller()