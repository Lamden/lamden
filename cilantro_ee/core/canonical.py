from .top import TopBlockManager
import os
import capnp
from cilantro_ee.messages import capnp as schemas
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


def block_from_subblocks(subblocks, top: TopBlockManager=TopBlockManager()):
    block_hasher = hashlib.sha3_256()
    block_hasher.update(top.get_latest_block_hash())

    for subblock in subblocks:
        sb = subblock.to_dict()

        sb = format_dictionary(sb)

        encoded_sb = bson.dumps(sb)

        block_hasher.update(encoded_sb)

    block_hash = block_hasher.digest()
    block_num = top.get_latest_block_number() + 1

