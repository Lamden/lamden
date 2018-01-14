import pika
from wallets import basic_wallet as wallet

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.queue_declare(queue='transactions')


(s, v) = wallet.new()
(s2, v2) = wallet.new()

tx = transaction.build(to=v2, amount=50, s=s, v=v)
tx2 = transaction.build(to=v, amount=500, s=s2, v=v2)

print(transaction.check_proof(tx['payload'], tx['metadata']['proof']))
print(transaction.check_proof(tx['payload'], '00000000000000000000000000000000'))

channel.basic_publish(exchange='',
                      routing_key='transactions',
                      body=tx,
                      properties=pika.BasicProperties(
                      		delivery_mode = 2,
                      	))
	#print(" [x] Sent {}", data)

connection.close()