import zmq
from wallets import basic_wallet as wallet
from transactions import basic_transaction as transaction
from serialization import basic_serialization

def main():
	context = zmq.Context()

	# Socket to receive messages on
	sender = context.socket(zmq.REQ)
	sender.connect("tcp://localhost:5555")

	(s, v) = wallet.new()
	(s2, v2) = wallet.new()

	tx = transaction.build(to=v2, amount=50, s=s, v=v)
	tx2 = transaction.build(to=v, amount=500, s=s2, v=v2)

	tx2['metadata']['proof'] = '00000000000000000000000000000000'

	sender.send_string(basic_serialization.serialize(tx))

	message = sender.recv()
	print("Received reply %s" % ( message))

	sender.send_string(basic_serialization.serialize(tx2))

	message = sender.recv()
	print("Received reply %s" % ( message))

def pusher():
	import secrets
	context = zmq.Context()

	# Socket with direct access to the sink: used to syncronize start of batch
	sink = context.socket(zmq.PUSH)
	sink.connect("tcp://localhost:5558")

	(s, v) = wallet.new()
	(s2, v2) = wallet.new()

	tx = transaction.build(to=v2, amount=50, s=s, v=v)
	tx2 = transaction.build(to=v, amount=500, s=s2, v=v2)

	tx2['metadata']['proof'] = '00000000000000000000000000000000'

	sink.send_string(basic_serialization.serialize(tx))
	sink.send_string(basic_serialization.serialize(tx2))

if __name__ == "__main__":
	pusher()