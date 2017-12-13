import sqlite3
import os

REFRESH_DB = True
DB_NAME = 'blockchain.db'
DB_PATH = os.path.join(os.getcwd(), DB_NAME)

if REFRESH_DB:
	os.remove(DB_PATH)

def create_tables():
	connection, cursor = connect()
	cursor.execute('''CREATE TABLE wallets 
		(key text primary key, 
		balance real)'''
	)
	connection.commit()
	connection.close()

def connect():
	connection = sqlite3.connect(DB_NAME)
	cursor = connection.cursor()
	return connection, cursor

def insert_wallet(s):
	connection, cursor = connect()
	cursor.execute("INSERT INTO wallets VALUES (?, ?)", (s, 0))
	connection.commit()
	connection.close()

def select_wallet(s):
	connection, cursor = connect()
	cursor.execute("SELECT * FROM wallets WHERE key = ?", (s,))
	return cursor.fetchone()

def mint_coins(s, v):
	connection, cursor = connect()
	cursor.execute("UPDATE wallets SET balance = ? WHERE key = ?", (v, s))
	connection.commit()
	connection.close()