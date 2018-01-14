import pika
from transactions import basic_transaction as transaction
from serialization import basic_serialization as s

def main():
	connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
	channel = connection.channel()

	channel.queue_declare(queue='transactions')

	def callback(ch, method, properties, body):
	    tx = s.deserialize(body)
	    if (transaction.check_proof(tx['payload'], tx['metadata']['proof'])) == True:
	    	print('transaction works!')
	    else:
	    	print('transaction does not work!')

	channel.basic_qos(prefetch_count=1)
	channel.basic_consume(callback,
	                      queue='transactions',
	                      no_ack=True)

	print(' [*] Waiting for messages. To exit press CTRL+C')
	channel.start_consuming()

if __name__ == "__main__":
	main()