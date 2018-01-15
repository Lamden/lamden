import sys
import time
import zmq
from transactions import basic_transaction as transaction
from serialization import basic_serialization

def test_zmq():
	context = zmq.Context()

	# Socket to receive messages on
	receiver = context.socket(zmq.REP)
	receiver.bind("tcp://*:5555")

	# Process tasks forever
	while True:
	    s = receiver.recv()
	    tx = basic_serialization.deserialize(s)

	    if (transaction.check_proof(tx['payload'], tx['metadata']['proof'])) == True:
	    	receiver.send_string('success')
	    else:
	    	receiver.send_string('failure')
	    print(s)

if __name__ == "__main__":
	test_zmq()