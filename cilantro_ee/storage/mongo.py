import os, time
from cilantro_ee.utils.utils import MongoTools
from cilantro_ee.messages.block_data.block_data import GenesisBlockData


class MDB:

    def create_genesis_blk(cls):
        # create insert genesis blk
        block = GenesisBlockData.create(sk = cls.sign_key, vk = cls.verify_key)
        cls.init_mdb = cls.insert_block(block_dict=block._data.to_dict())
        assert cls.init_mdb is True, "failed to create genesis block"

        cls.log.debugv('start_db init set {}'.format(cls.init_mdb))

        # update index record
        if cls.init_mdb is True:
            idx = {'blockNum': block.block_num, 'blockHash': block.block_hash, 'blockOwners': cls.verify_key,
                   'ts': time.time()}
            cls.log.debugv('start_db init index {}'.format(idx))
            return cls.insert_idx_record(my_dict = idx)

    '''
        Wr to store or index
    '''
    @classmethod
    def insert_block(cls, block_dict=None):
        if block_dict is None:
            return False

        # insert passed dict block to db
        blk_id = cls.mn_collection.insert_one(block_dict)
        cls.log.spam("block {}".format(block_dict))
        if blk_id:
            return True

    @classmethod
    def insert_idx_record(cls, my_dict=None):
        if dict is None:
            return None
        idx_entry = cls.mn_coll_idx.insert_one(my_dict)
        cls.log.spam("insert_idx_record -> {}".format(idx_entry))
        return True

    @classmethod
    def insert_tx_map(cls, txmap):
        obj = cls.mn_coll_tx.insert_one(txmap)
        cls.log.debugv("insert_idx_record -> {}".format(obj))


    @classmethod
    def query_db(cls, type=None, query=None):
        result = {}
        if query is None:
            if type is None or type is "MDB":
                block_list = cls.mn_collection.find({})
                for x in block_list:
                    result.update(x)
                    cls.log.spam("from mdb {}".format(x))

            if type is None or type is "idx":
                index_list = cls.mn_coll_idx.find({})
                for y in index_list:
                    result.update(y)
                    cls.log.spam("from idx {}".format(y))
        else:
            if type is 'idx':
                dump = cls.mn_coll_idx.find(query)
                cls.log.debug("Mongo tools count {}".format(MongoTools.get_count(dump)))
                assert MongoTools.get_count(dump) != 0, "lookup failed count is 0 dumping result-{} n query-{}"\
                    .format(dump, query)
                for x in dump:
                    result.update(x)
                cls.log.debug("result {}".format(result))

            if type is 'MDB':
                outcome = cls.mn_collection.find(query)
                for x in outcome:
                    result.update(x)
                    cls.log.spam("result {}".format(x))

            if type is 'tx':
                outcome = cls.mn_coll_tx.find(query)
                count = 0
                for x in outcome:
                    # cls.log.important2("RESULT X {} count {}".format(x, MongoTools.get_count(result)))
                    result.update(x)
                    count = count + 1
                # assert result != 1, "we have duplicate transactions dumping result {}".format(result)
                if count > 1:
                    cls.log.error("we have duplicate transaction results {}".format(result))

        if len(result) > 0:
            # cls.log.important("result => {}".format(result))
            return result
        else:
            cls.log.spam("result => {}".format(result))
            return None

    @classmethod
    def query_store(cls, blk_num=None):
        """
        Returns locally stored block by blk_num
        :param blk_num:
        :return:
        """
        response = cls.mn_collection.find(blk_num)

        if response is None:
            cls.log.error('given blk not present in db')
            return

        return response
