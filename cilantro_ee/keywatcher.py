## functions for 'listening' to state changes so that the protocol can react to them
from contracting.db.encoder import make_key, decode


def extract_deltas(block, contract, variable, keys=[]):
    deltas = []
    key = make_key(contract=contract, variable=variable, keys=keys).encode()
    for sub_block in block['subBlocks']:
        for transaction in sub_block['transactions']:
            for delta in transaction['state']:
                if delta['key'] == key:
                    deltas.append(decode(delta['value']))

    return deltas

