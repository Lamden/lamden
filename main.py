import sqlite3
import os
from ecdsa import SigningKey

REFRESH_DB = True
DB_NAME = 'blockchain.db'
DB_PATH = os.path.join(os.getcwd(), DB_NAME)

if REFRESH_DB:
	os.remove(DB_PATH)

connection = sqlite3.connect(DB_NAME)
cursor = connection.cursor()

cursor.execute('''CREATE TABLE wallets 
	(key text, 
	balance real)'''
)

def generate_keys():
	# generates a tuple keypair
	sk = SigningKey.generate()
	vk = sk.get_verifying_key()
	return (sk, vk)

def keys_to_format(s, v):
	# turns binary data into desired format
	s = s.to_string()
	v = v.to_string()
	return (s.hex(), v.hex())

def format_to_keys(s, v):
	# returns the human readable format to bytes for processing
	return(bytes.fromhex(s), bytes.fromhex(v))

def new_wallet():
	# interface to creating a new wallet
	s, v = generate_keys()
	return keys_to_format(s, v)


(pubkey, privkey) = new_wallet()
print(pubkey)
print(privkey)