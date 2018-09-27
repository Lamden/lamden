from cilantro.storage.sqldb import SQLDB
from cilantro.messages.block_data.block_data import BlockData
from cilantro.messages.block_data.block_metadata import FullBlockMetaData
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
import dill, ujson as json, textwrap
from typing import List
from cilantro.utils import Hasher
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.transaction.contract import ContractTransaction

def chunk(s):
    assert len(s) % 64 == 0, 'Malformed'
    return [s[i*64:(i+1)*64].decode() for i in range(int(len(s)/64))]

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
        return {
            'block_num': sql_obj[0],
            'block_hash': sql_obj[1].decode(),
            'merkle_roots': chunk(sql_obj[2]),
            'prev_block_hash': sql_obj[3].decode(),
            'masternode_signature': MerkleSignature.from_bytes(sql_obj[4]),
            'timestamp': sql_obj[5].timestamp()
        }

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
                'i am at an unstable state' # WARNING change this
            ))
        return txs

    @classmethod
    def unpack(cls, sql_obj):
        txs = []
        for tx in sql_obj:
            txs.append({
                'tx_hash': tx[0],
                'block_hash': tx[1],
                'raw_tx_hash': tx[2],
                'contract_tx': ContractTransaction.from_bytes(tx[3]),
                'status': tx[4],
                'state': tx[5]
            })
        return txs

class SubBlockMetaSQL:
    @classmethod
    def pack(cls, sub_block, signatures):
        return (
            sub_block.result_hash,
            json.dumps([sig.serialize() for sig in signatures]),
            ''.join(sub_block.merkle_leaves),
            sub_block.sb_index
        )

    @classmethod
    def unpack(cls, sql_obj):
        return {
            'merkle_root': sql_obj[0].decode(),
            'signatures': [MerkleSignature.from_bytes(sig.encode()) for sig in json.loads(sql_obj[1])],
            'merkle_leaves': chunk(sql_obj[2]),
            'sb_index': sql_obj[3]
        }

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
                    INSERT INTO transaction (block_hash, tx_hash, raw_tx_hash, contract_tx, status, state)
                        VALUES (%s, %s, %s, %s, %s, %s)
                """, BlockTransactionsSQL.pack(block))

            except:
                connection.rollback()
                raise Exception('Unable to commit the block to the database!')

    @classmethod
    def store_sub_block(cls, sbc: SubBlockContender, signatures: List[MerkleSignature]):
        with SQLDB() as (connection, cursor):
            cursor.execute("""
                INSERT INTO sub_block (merkle_root, signatures, merkle_leaves, sb_index)
                    VALUES (%s,%s,%s,%s)
            """, SubBlockMetaSQL.pack(sbc, signatures))

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
    def get_sub_block_meta(cls, merkle_root):
        with SQLDB() as (connection, cursor):
            cursor.execute("""
                SELECT * FROM sub_block
                    WHERE merkle_root = %s
            """, (merkle_root,))
            res = cursor.fetchone()
            if res:
                return SubBlockMetaSQL.unpack(res)

    @classmethod
    def get_transactions(cls, block_hash=None, raw_tx_hash=None, status=None):
        with SQLDB() as (connection, cursor):
            conds = []
            params = ()
            if block_hash:
                conds.append('block_hash = %s')
                params += (block_hash,)
            if raw_tx_hash:
                conds.append('raw_tx_hash = %s')
                params += (raw_tx_hash,)
            if status:
                conds.append('status = %s')
                params += (status,)
            q_str = 'WHERE {}'.format(' AND '.join(conds)) if len(conds) > 0 else ''
            cursor.execute("SELECT * FROM transaction {}".format(
                q_str), params)
            res = cursor.fetchall()
            if res:
                return BlockTransactionsSQL.unpack(res)

    @classmethod
    def get_latest_blocks(cls, start_block_hash):
        pass
