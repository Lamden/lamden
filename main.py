from wallets import basic_wallet as wallet
import db
from transactions import basic_transaction as transaction
import pprint

def test_db_and_wallet():
	# create a new local datastore
	db.create_tables()
	connection, cursor = db.connect()

	# create and insert a new wallet
	(s, v) = wallet.new()
	db.insert_wallet(s)

	# mint some coins and verify it has them
	db.mint_coins(s, 100)
	print(db.select_wallet(s))

	# create and insert a new wallet and verify it has no coins
	(s2, v2) = wallet.new()
	db.insert_wallet(s2)
	print(db.select_wallet(s2))

def test_sign_and_verify():
	# transactions should become protocol buffers, but for now they are JSON
	# create and insert a new wallet
	(s, v) = wallet.new()
	(s2, v2) = wallet.new()

	msg = b'hello there'
	sig = wallet.sign(s, msg)
	print(wallet.verify(v, msg, sig))
	print(wallet.verify(v2, msg, sig))

def test_transaction():
	(s, v) = wallet.new()
	(s2, v2) = wallet.new()

	tx = transaction.build(to=v2, amount=50, s=s, v=v)
	pprint.pprint(tx)

	print(transaction.check_proof(tx['payload'], tx['metadata']['proof']))
	print(transaction.check_proof(tx['payload'], '00000000000000000000000000000000'))

(s, v) = wallet.new()
(s2, v2) = wallet.new()

tx = transaction.build(to=v2, amount=50, s=s, v=v)
from serialization import basic_serialization
s = basic_serialization.serialize(tx)
t = basic_serialization.deserialize(s)

#print(s)
print(t)
print(tx)
#4CQ8f6c9H2qFL7H3VVNVxVXar2ordtDetc9EJ9nXkC966ryCRb4hz1fcNiR1g6K76W