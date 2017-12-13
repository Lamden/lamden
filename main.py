import sqlite3
import os
import wallet
import db

cursor = db.get_cursor()

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

cursor.execute("SELECT * FROM wallets WHERE key = ?", (s,))
print(cursor.fetchone())

(s2, k2) = wallet.new()
cursor.execute("INSERT INTO wallets VALUES (?, ?)", (s2, 0))
cursor.execute("SELECT * FROM wallets WHERE key = ?", (s2,))
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