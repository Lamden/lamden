from cilantro_ee.storage.mongo import MDB
from cilantro_ee.messages.block_data.block_data import BlockData


class MasterOps:
    @classmethod
    def update_tx_map(cls, block: BlockData):
        map = block.get_tx_hash_to_merkle_leaf()
        blk_id = block.block_num

        # cls.log.important2("Tx map - {}".format(len(map)))
        for entry in map:
            entry['block'] = blk_id
            # cls.log.important2("Entry - {}".format(entry))
            MDB.insert_tx_map(txmap = entry)

    @classmethod
    def get_usr_tx_result(cls, usr_tx_hash):
        my_query = {'tx_hash': usr_tx_hash}
        outcome = MDB.query_db(type='tx', query = my_query)
        cls.log.debugv("print outcome {}".format(outcome))
        return outcome
