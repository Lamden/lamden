import wallet
import db

# create a new local datastore
db.create_tables()
connection, cursor = db.connect()

# create and insert a new wallet
(s, k) = wallet.new()
db.insert_wallet(s)

# mint some coins and verify it has them
db.mint_coins(s, 100)
print(db.select_wallet(s))

# create and insert a new wallet and verify it has no coins
(s2, k2) = wallet.new()
db.insert_wallet(s2)
print(db.select_wallet(s2))