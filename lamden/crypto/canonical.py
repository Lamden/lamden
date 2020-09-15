import json
from copy import deepcopy

import hashlib

from contracting.db.encoder import encode

from lamden.logger.base import get_logger

log = get_logger('CANON')


GENESIS_HASH = b'\x00' * 32


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


def tx_hash_from_tx(tx):
    h = hashlib.sha3_256()
    tx_dict = format_dictionary(tx)
    encoded_tx = encode(tx_dict).encode()
    h.update(encoded_tx)
    return h.hexdigest()


def merklize(leaves):
    # Make space for the parent hashes
    nodes = [None for _ in range(len(leaves) - 1)]

    # Hash all leaves so that all data is same length
    for l in leaves:
        h = hashlib.sha3_256()
        h.update(l)
        nodes.append(h.digest())

    # Hash each pair of leaves together and set the hash to their parent in the list
    for i in range((len(leaves) * 2) - 1 - len(leaves), 0, -1):
        h = hashlib.sha3_256()
        h.update(nodes[2 * i - 1] + nodes[2 * i])
        true_i = i - 1
        nodes[true_i] = h.digest()

    # Return the list
    return [n.hex() for n in nodes]


def verify_merkle_tree(leaves, expected_root):
    tree = merklize(leaves)

    if tree[0] == expected_root:
        return True
    return False


def block_from_subblocks(subblocks, previous_hash: str, block_num: int) -> dict:
    block_hasher = hashlib.sha3_256()
    block_hasher.update(bytes.fromhex(previous_hash))

    deserialized_subblocks = []

    for subblock in subblocks:
        if subblock is None:
            continue

        sb = format_dictionary(subblock)
        deserialized_subblocks.append(sb)

        sb_without_sigs = deepcopy(sb)
        if sb_without_sigs.get('signatures') is not None:
            del sb_without_sigs['signatures']

        encoded_sb = encode(sb_without_sigs)

        block_hasher.update(encoded_sb.encode())

    block = {
        'hash': block_hasher.digest().hex(),
        'number': block_num,
        'previous': previous_hash,
        'subblocks': deserialized_subblocks
    }

    return block