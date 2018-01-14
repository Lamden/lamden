from wallets import basic_wallet as wallet
import db
from transactions import basic_transaction as transaction
import pprint
import hashlib

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

# testing id building a transaction works
def test_transaction():
	(s, v) = wallet.new()
	(s2, v2) = wallet.new()

	tx = transaction.build(to=v2, amount=50, s=s, v=v)
	pprint.pprint(tx)

	print(transaction.check_proof(tx['payload'], tx['metadata']['proof']))
	print(transaction.check_proof(tx['payload'], '00000000000000000000000000000000'))

# testing if a message can be serialized back and forth.
def test_basic_serialization():
	(s, v) = wallet.new()
	(s2, v2) = wallet.new()

	tx = transaction.build(to=v2, amount=50, s=s, v=v)
	from serialization import basic_serialization
	s = basic_serialization.serialize(tx)
	t = basic_serialization.deserialize(s)

	#print(s)
	print(t)
	print(tx)



def signing():
	block_data = b'BLOCK_DATA'

	sha3 = hashlib.sha3_256()
	sha3.update(block_data)
	print(sha3.digest())

	signatures = []
	wallets = []

	for x in range(8):
		print('signing...')
		(s, v) = wallet.new()
		wallets.append(v)
		signatures.append(wallet.sign(s, block_data))

	for x in range(8):
		v = wallets[x]
		sig = signatures[x]
		print(wallet.verify(v, block_data, sig))

	print(signatures)

from networking import node
node.test_transactions()