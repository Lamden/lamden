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

def hash_from_results(formatted_results):
    h = hashlib.sha3_256()
    encoded_tx = encode(formatted_results).encode()
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
    # block_hasher.update(bytes.fromhex(previous_hash))

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

def block_from_tx_results(processing_results, proofs, block_num, prev_block_hash) -> dict:
    tx_result = processing_results.get('tx_result')
    hlc_timestamp = processing_results.get('hlc_timestamp')

    pruned_proofs = remove_result_hash_from_proofs(proofs)
    block_hash = block_hash_from_block(
        hlc_timestamp=hlc_timestamp,
        block_number=block_num,
        previous_block_hash=prev_block_hash
    )

    block = {
        'hash': block_hash,
        'number': block_num,
        'hlc_timestamp': hlc_timestamp,
        'previous': prev_block_hash,
        'proofs': pruned_proofs,
        'processed': tx_result,
        'rewards': processing_results.get('rewards'),
        'origin': processing_results.get('tx_message')
    }

    return block

def block_hash_from_block(hlc_timestamp: str, block_number: int, previous_block_hash: str) -> str:
    h = hashlib.sha3_256()
    h.update('{}{}{}'.format(hlc_timestamp, block_number, previous_block_hash).encode())
    return h.hexdigest()

def recalc_block_info(block, new_block_num, new_prev_hash) -> dict:
    hlc_timestamp = block.get('hlc_timestamp')

    h = hashlib.sha3_256()

    h.update('{}{}{}'.format(hlc_timestamp, new_block_num, new_prev_hash).encode())

    block['hash'] = h.hexdigest()
    block['previous'] = new_prev_hash
    block['number'] = new_block_num

    return block

def remove_result_hash_from_proofs(proofs) -> list:
    for proof in proofs:
        try:
            del proof['tx_result_hash']
        except KeyError:
            pass

    return proofs

def tx_result_hash_from_tx_result_object(tx_result, hlc_timestamp, rewards):
    h = hashlib.sha3_256()
    h.update('{}'.format(encode(tx_result).encode()).encode())
    h.update('{}'.format(encode(rewards).encode()).encode())
    h.update('{}'.format(hlc_timestamp).encode())
    return h.hexdigest()
