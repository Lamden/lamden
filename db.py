import sqlite3
import os

REFRESH_DB = True
DB_NAME = 'blockchain.db'
DB_PATH = os.path.join(os.getcwd(), DB_NAME)

if REFRESH_DB:
	try:
		os.remove(DB_PATH)
	except:
		pass

print('booty')

def get_cursor():
	connection = sqlite3.connect(DB_NAME)
	cursor = connection.cursor()
	return cursor