import os
import capnp
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
import bson
import hashlib

subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')
block_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')


def format_dictionary(d: dict) -> dict:
    for k, v in d.items():
        assert type(k) == str, 'Non-string key types not allowed.'
        if type(v) == list:
            for i in range(len(v)):
                if isinstance(v[i], dict):
                    v[i] = format_dictionary(v[i])
        elif isinstance(v, dict):
            d[k] = format_dictionary(v)
    return {k: v for k, v in sorted(d.items())}


def block_from_subblocks(subblocks, previous_hash: bytes, block_num: int) -> dict:
    block_hasher = hashlib.sha3_256()
    block_hasher.update(previous_hash)

    deserialized_subblocks = []

    for subblock in subblocks:
        if subblock is None:
            sb = {}
        else:
            sb = subblock.to_dict()

        sb = format_dictionary(sb)
        deserialized_subblocks.append(sb)

        encoded_sb = bson.BSON.encode(sb)
        block_hasher.update(encoded_sb)

    block = {
        'blockHash': block_hasher.digest(),
        'blockNum': block_num,
        'prevBlockHash': previous_hash,
        'subBlocks': deserialized_subblocks
    }

    return block


def verify_block(subblocks, previous_hash: bytes, proposed_hash: bytes):
    # Verify signatures!
    block_hasher = hashlib.sha3_256()
    block_hasher.update(previous_hash)

    deserialized_subblocks = []

    for subblock in subblocks:
        sb = subblock.to_dict()

        sb = format_dictionary(sb)
        deserialized_subblocks.append(sb)

        encoded_sb = bson.BSON.encode(sb)
        block_hasher.update(encoded_sb)

    if block_hasher.digest() == proposed_hash:
        return True

    return False


def block_is_skip_block(block: dict):
    for subblock in block['subBlocks']:
        if len(subblock.transactions):
            return False
    return True


def get_failed_block(previous_hash: bytes, block_num: int) -> dict:
    block = {
        'blockHash': b'\x00' * 32,
        'blockNum': block_num,
        'prevBlockHash': previous_hash,
        'subBlocks': None
    }
    return block


def block_is_failed(block, previous_hash: bytes, block_num: int):
    if block['blockHash'] != b'\x00' * 32:
        return False

    if block['subBlocks'] is not None:
        return False

    if block['blockNum'] != block_num:
        return False

    if block['prevBlockHash'] != previous_hash:
        return False

    return True


def message_blob_to_dict_block(block):
    pass


def capnp_to_dict_block(block):
    return block_capnp.BlockData.to_dict(block)
