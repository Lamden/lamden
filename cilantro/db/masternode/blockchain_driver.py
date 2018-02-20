from pymongo import MongoClient
from cilantro.db.constants import MONGO
import json
import hashlib
from cilantro.serialization import JSONSerializer
from cilantro.transactions.testnet import TestNetTransaction

# DEBUG TODO -- remove these import
import os

class BlockchainDriver(object):

    def __init__(self, mongo_uri='mongodb://localhost:27017/', serializer=JSONSerializer):
        client = MongoClient(mongo_uri)
        db = client[MONGO.db_name]
        self.blocks = db[MONGO.blocks_col_name]
        self.state = db[MONGO.blocks_state_col_name]
        self.balances = db[MONGO.balances_col_name]
        self.serializer = JSONSerializer

    def persist_block(self, block: dict):
        """
        Attempts to persist the block, represented as a python dictionary. Raises an exception if something fails
        :param block: The block as a python dictionary

        TODO -- make a custom block data structure
        """
        # Add block number and block hash
        all_tx = block['transactions']
        block_num = self.inc_block_number()
        h = hashlib.sha3_256()
        h.update(self.serializer.serialize(all_tx) + block_num.to_bytes(8, 'little'))
        block['block_num'] = block_num
        block['hash'] = h.hexdigest()

        # Get and update last block hash
        last_hash = self.state.find_one({MONGO.latest_hash_key: {'$exists': True}})
        new_hash = block['hash']
        if last_hash is None:
            raise Exception("Could not find latest hash. Was genesis block created?")
        else:
            self.state.update_one(last_hash, {'$set': {MONGO.latest_hash_key: new_hash}})
            last_hash = last_hash[MONGO.latest_hash_key]
        block['previous_hash'] = last_hash

        self.blocks.insert_one(block)

        # Update balances
        for tx in all_tx:
            self.update_balance(tx)

    def create_genesis(self):
        # Make sure genesis block does not already exist
        if self.blocks.find_one({MONGO.genesis_key: {'$exists': True}}) is not None:
            # raise Exception("Genesis block already exists!")
            print("Genesis block already exists, skipping creation.")
            return

        # Sanity check, ensure block number is one (which should be the case only if no blocks have been persisted yet)
        block_num = self.inc_block_number()
        if block_num != 1:
            raise Exception("Block number {} is not 1 for genesis block!".format(block_num))

        file_path = os.getcwd() + '/cilantro/db/masternode/genesis.json'
        block = {}
        genesis_json = json.load(open(file_path))
        block[MONGO.genesis_key] = True
        block['block_num'] = block_num
        block['hash'] = genesis_json['hash']
        block['previous_hash'] = None
        block['alloc'] = genesis_json['alloc']

        # Set balances to initial genesis alloc
        if self.balances.count() != 0:
            raise Exception("Balances collection not empty during genesis block creation")
        for wallet, balance in block['alloc'].items():
            self.balances.insert_one({MONGO.wallet_key: wallet, MONGO.balance_key: balance})

        self.state.insert_one({MONGO.latest_hash_key: block['hash']})
        self.blocks.insert_one(block)
        print("Inserted genesis block with alloc: {}".format(block['alloc']))

    def update_balance(self, tx: list):
        """
        Updates the balance collection to reflect the outcome of the transaction
        :param tx: A list representing the transaction
        """
        print("updating balance for tx: {}".format(tx))

        tx_type = tx[0]
        if tx_type == TestNetTransaction.TX:
            sender_adr, receiver_adr, amount = tx[1], tx[2], tx[3]
            amount = float(amount)
            sender = self.balances.find_one({MONGO.wallet_key: sender_adr})

            if sender is None:
                raise Exception("Sender address {} could not be found in balances (tx={})".format(sender_adr, tx))

            # Update sender and receiver balance
            self.balances.update_one({MONGO.wallet_key: sender_adr}, {'$inc': {MONGO.balance_key: -amount}})
            self.balances.update_one({MONGO.wallet_key: receiver_adr},
                                     {'$inc': {MONGO.balance_key: amount}}, upsert=True)

        elif tx_type == TestNetTransaction.VOTE:
            raise NotImplementedError
        elif tx_type == TestNetTransaction.STAMP:
            raise NotImplementedError
        elif tx_type == TestNetTransaction.SWAP:
            raise NotImplementedError
        elif tx_type == TestNetTransaction.REDEEM:
            raise NotImplementedError
        else:
            raise Exception("Unknown transaction type {} processed by blockchain_driver".format(tx_type))

    def inc_block_number(self) -> int:
        """
        Increments the latest block number and returns it
        :return: The latest block number, as an integer
        """
        block_num = self.state.find_one({MONGO.latest_block_num_key: {'$exists': True}})
        if block_num is None:
            block_num = 1
            self.state.insert_one({MONGO.latest_block_num_key: block_num})
        else:
            block_num = int(block_num[MONGO.latest_block_num_key])
            block_num += 1
            self.state.update_one({MONGO.latest_block_num_key: {'$exists': True}},
                                  {'$set': {MONGO.latest_block_num_key: block_num}})
        return block_num





