import pika
from wallets import basic_wallet as wallet
from transactions import basic_transaction as transaction
from serialization import basic_serialization

# build 2 transactions and send them to the witness
def test_transactions():
	connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
	channel = connection.channel()

	channel.queue_declare(queue='transactions')


	(s, v) = wallet.new()
	(s2, v2) = wallet.new()

	tx = transaction.build(to=v2, amount=50, s=s, v=v)
	tx2 = transaction.build(to=v, amount=500, s=s2, v=v2)

	tx2['metadata']['proof'] = '00000000000000000000000000000000'

	print(tx)

	channel.basic_publish(exchange='',
	                      routing_key='transactions',
	                      body=basic_serialization.serialize(tx),
	                      properties=pika.BasicProperties(
	                      		delivery_mode = 2,
	                      	))

	channel.basic_publish(exchange='',
	                      routing_key='transactions',
	                      body=basic_serialization.serialize(tx2),
	                      properties=pika.BasicProperties(
	                      		delivery_mode = 2,
	                      ))

	connection.close()

if __name__ == "__main__":
	test_transactions()