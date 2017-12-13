import wallet
import db

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


# transactions should become protocol buffers, but for now they are JSON
# create and insert a new wallet
(s, v) = wallet.new()

msg = b'hello there'
sig = wallet.sign(s, msg)
wallet.verify(v, msg, sig)

transaction = {
	'payload' : {
		'to' : 'wallet',
		'amount' : 0
	},
	'metadata' : {
		'proof' : '000',
		'signature' : '000'
	}
}

