from .top import TopBlockManager
import os
import capnp
from cilantro_ee.core.messages.capnp_impl import capnp_struct as schemas
import bson
import hashlib

subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')


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


def block_from_subblocks(subblocks, top: TopBlockManager=TopBlockManager()) -> dict:
    block_hasher = hashlib.sha3_256()
    block_hasher.update(top.get_latest_block_hash())

    deserialized_subblocks = []

    for subblock in subblocks:
        sb = subblock.to_dict()

        sb = format_dictionary(sb)
        deserialized_subblocks.append(sb)

        encoded_sb = bson.dumps(sb)
        block_hasher.update(encoded_sb)

    block = {
        'blockHash': block_hasher.digest(),
        'blockNum': top.get_latest_block_number() + 1,
        'prevBlockHash': top.get_latest_block_hash(),
        'subBlocks': deserialized_subblocks
    }

    return block


def verify_block(subblocks, previous_hash: bytes, proposed_hash: bytes):
    block_hasher = hashlib.sha3_256()
    block_hasher.update(previous_hash)

    deserialized_subblocks = []

    for subblock in subblocks:
        sb = subblock.to_dict()

        sb = format_dictionary(sb)
        deserialized_subblocks.append(sb)

        encoded_sb = bson.dumps(sb)
        block_hasher.update(encoded_sb)

    if block_hasher.digest() == proposed_hash:
        return True
    return False
