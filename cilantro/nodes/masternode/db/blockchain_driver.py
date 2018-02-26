from pymongo import MongoClient, ReturnDocument, ASCENDING
from cilantro.utils.constants import MONGO
import json
import hashlib
from cilantro.protocol.serialization import JSONSerializer
from cilantro.protocol.transactions.testnet import TestNetTransaction

# DEBUG TODO -- remove these import
import os

class BlockchainDriver(object):

    def __init__(self, mongo_uri='mongodb://localhost:27017/', serializer=JSONSerializer):
        client = MongoClient(mongo_uri)
        db = client[MONGO.db_name]
        self.blocks = db[MONGO.blocks_col_name]
        self.state = db[MONGO.blocks_state_col_name]
        self.balances = db[MONGO.balances_col_name]
        self.faucet = db[MONGO.faucet_col_name]
        self.serializer = JSONSerializer

        faucet_path = os.getcwd() + '/cilantro/faucet.json'
        faucet_json = json.load(open(faucet_path))
        self.faucet_v = faucet_json['verifying_key']

    def persist_block(self, block: dict) -> dict:
        """
        Attempts to persist the block, represented as a python dictionary. Raises an exception if something fails
        :param block: The block as a python dictionary
        :return: A dictionary containing all the wallets keys and new amounts updated as a result of the block in the
        form of {wallet_key1: new_amount1, wallet_key2: new_amount2, ...}

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
        updates = {}
        for tx in all_tx:
            for wallet, balance in self.update_balance(tx).items():
                updates[wallet] = balance
        return updates

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

        file_path = os.getcwd() + '/cilantro/db/db/genesis.json'
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

    def get_balance(self, wallet_key):
        balance = self.balances.find_one({MONGO.wallet_key: wallet_key})
        if balance is None:
            print("Balance not found for wallet key: {}, returning 0".format(wallet_key))
            return {wallet_key: 0}
        return {wallet_key: balance[MONGO.balance_key]}

    def get_all_balances(self):
        balances = {}
        for b in self.balances.find({}):
            balances[b[MONGO.wallet_key]] = b[MONGO.balance_key]
        return balances

    def update_balance(self, tx: list) -> dict:
        """
        Updates the balance collection to reflect the outcome of the transaction
        :param tx: A list representing the transaction
        :return: A dictionary of updated balances in the form {wallet1: new_balance1, wallet2: new_balance2, ...}
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
            sender_new = self.balances.find_one_and_update({MONGO.wallet_key: sender_adr},
                                                           {'$inc': {MONGO.balance_key: -amount}},
                                              return_document=ReturnDocument.AFTER)
            receiver_new = self.balances.find_one_and_update({MONGO.wallet_key: receiver_adr},
                                              {'$inc': {MONGO.balance_key: amount}},
                                              upsert=True, return_document=ReturnDocument.AFTER)

            return {sender_adr: sender_new[MONGO.balance_key], receiver_adr: receiver_new[MONGO.balance_key]}

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

    def check_faucet_used(self, wallet_key) -> bool:
        return self.faucet.find_one({wallet_key: True}) is not None

    def add_faucet_use(self, wallet_key):
        self.faucet.insert_one({wallet_key: True})

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

    def get_blockchain_data(self) -> str:
        """
        Returns blockchain data for client size viz
        """
        keys = ('sender', 'receiver', 'amount', 'time', 'block_hash', 'block_num')
        csv = ",".join(keys) + "\r\n"

        for block in self.blocks.find({MONGO.genesis_key: {'$exists': False}}, {"_id": 0}).sort('block_num', ASCENDING):
            for tx in block['transactions']:
                sender = tx[1]
                # Exclude faucet transactions
                if sender == self.faucet_v:
                    continue
                receiver = tx[2]
                amount = str(tx[3])
                time = str(tx[4])
                hash = block['hash']
                block_num = str(block['block_num'])
                csv += ",".join((sender, receiver, amount, time, hash, block_num)) + "\r\n"

        return csv


