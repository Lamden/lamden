import sqlite3
import rsa
import os

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

def new_wallet():
	return rsa.newkeys(512, poolsize=8)

(pubkey, privkey) = new_wallet()
print(pubkey)