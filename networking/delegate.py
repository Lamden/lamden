import pika

def main():
	connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
	channel = connection.channel()

	channel.queue_declare(queue='verified_transactions')

	def callback(ch, method, properties, body):
	    print('recieved a verified transaction')

	channel.basic_qos(prefetch_count=1)
	channel.basic_consume(callback,
	                      queue='verified_transactions',
	                      no_ack=True)

	print(' [*] Waiting for messages. To exit press CTRL+C')
	channel.start_consuming()

if __name__ == "__main__":
	main()