from cilantro.storage.sqldb import SQLDB
from cilantro.messages.block_data.block_data import BlockData
from cilantro.messages.block_data.block_metadata import FullBlockMetaData
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
import dill, ujson as json, textwrap
from cilantro.utils import Hasher
from cilantro.messages.consensus.merkle_signature import MerkleSignature

class BlockMetaSQL:
    @classmethod
    def pack(cls, block):
        return (
            block.block_hash,
            ''.join(block.merkle_roots),
            block.prev_block_hash,
            block.masternode_signature.serialize()
        )

    @classmethod
    def unpack(cls, sql_obj):
        fbmd = FullBlockMetaData.create(
            block_num=sql_obj[0],
            block_hash=sql_obj[1].decode(),
            merkle_roots=textwrap.wrap(sql_obj[2].decode(), 64),
            prev_block_hash=sql_obj[3].decode(),
            masternode_signature=MerkleSignature.from_bytes(sql_obj[4]),
            timestamp=sql_obj[5].timestamp()
        )
        return fbmd

class BlockTransactionsSQL:
    @classmethod
    def pack(cls, block, chunks=4096):
        txs = []
        for tx in block.transactions:
            txs.append((
                block.block_hash,
                Hasher.hash(tx),
                Hasher.hash(tx.contract_tx),
                tx.contract_tx.serialize(),
                'SUCCESS', # WARNING change this
                'i am at an unstable state'
            ))
        return txs

class SubBlockMetaSQL:
    @classmethod
    def pack(cls, subblock):
        pass

class StorageDriver(object):
    @classmethod
    def store_block(cls, block: BlockData, validate: bool):
        if validate:
            block.validate()
        with SQLDB() as (connection, cursor):
            try:
                cursor.execute("""
                    INSERT INTO block (block_hash, merkle_roots, prev_block_hash, mn_signature)
                        VALUES (%s,%s,%s,%s)
                """, BlockMetaSQL.pack(block))

                cursor.executemany("""
                    INSERT INTO transaction (block_hash, tx_hash, raw_tx_hash, tx_blob, status, state)
                        VALUES (%s, %s, %s, %s, %s, %s)
                """, BlockTransactionsSQL.pack(block))

            except:
                connection.rollback()
                raise Exception('Unable to commit the block to the database!')

    @classmethod
    def store_sub_blocks(cls, sbc: SubBlockContender):
        with SQLDB() as (connection, cursor):
            pass

    @classmethod
    def get_block_meta(cls, block_hash):
        with SQLDB() as (connection, cursor):
            cursor.execute("""
                SELECT * FROM block
                    WHERE block_hash = %s
            """, (block_hash,))
            res = cursor.fetchone()
            if res:
                return BlockMetaSQL.unpack(res)

    @classmethod
    def get_latest_blocks(cls, start_block_hash):
        pass
