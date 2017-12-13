import sqlite3
import os
import wallet

REFRESH_DB = True
DB_NAME = 'blockchain.db'
DB_PATH = os.path.join(os.getcwd(), DB_NAME)

if REFRESH_DB:
	os.remove(DB_PATH)

connection = sqlite3.connect(DB_NAME)
cursor = connection.cursor()

cursor.execute('''CREATE TABLE wallets 
	(key text primary key, 
	balance real)'''
)

# create a new wallet
(s, k) = wallet.new()

# add it to the local database
cursor.execute("INSERT INTO wallets VALUES (?, ?)", (s, 0))

def set_coins(wallet, amount):
	cursor.execute("UPDATE wallets SET balance = ? WHERE key = ?", (amount, wallet))

set_coins(s, 100)
print(s)
cursor.execute("SELECT * FROM wallets WHERE key = ?", (s,))
print(cursor.fetchone())

# '''
# {
# 	to: '',
# 	amount: '',
# },
# {
# 	signature: '',
# 	proof: ''
# }
# '''