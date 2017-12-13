import sqlite3

REFRESH_DB = True

connection = sqlite3.connect('blockchain.db')
cursor = connection.cursor()

c.execute('''CREATE TABLE wallets 
	(key text, 
	balance real)'''
)

