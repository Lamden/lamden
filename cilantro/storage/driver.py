from cilantro.storage.sqldb import SQLDB

class StorageDriver(object):
    @classmethod
    def store_block(cls, block):
        pass

    @classmethod
    def store_sub_blocks(cls, subblocks):
        pass

    @classmethod
    def store_transactions(cls, transactions):
        pass

    @classmethod
    def get_latest_blocks(cls, start_block_hash):
        pass

    
