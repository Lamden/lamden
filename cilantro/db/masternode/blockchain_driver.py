from pymongo import MongoClient
from cilantro.db.constants import MONGO


class BlockchainDriver(object):

    def __init__(self, mongo_uri='mongodb://localhost:27017/'):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[MONGO.db_name]
        self.col = self.db[MONGO.col_name]

    def persist_block(self, block: dict):
        """
        Attempts to persist the block, represented as a python dictionary. Raises an exception if something fails
        :param block: The block as a python dictionary

        TODO -- make a custom block data structure
        """
        # Get and update last block hash
        last_hash = self.col.find_one({MONGO.latest_hash_key: {'$exists': True}})
        new_hash = block['hash']
        if last_hash is None:
            self.col.insert_one({MONGO.latest_hash_key: new_hash})
        else:
            self.col.update_one({MONGO.latest_hash_key: {'$exists': True}}, {'$set': {MONGO.latest_hash_key: new_hash}})

        self.col.insert_one({'hash': new_hash, 'previous_hash': last_hash, 'block': block['block']})

