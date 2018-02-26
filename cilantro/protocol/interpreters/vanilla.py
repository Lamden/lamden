VOTE = {'type': 'v', 'sender': None, 'key': None, 'value': None}
STD = {'type': 'v', 'sender': None, 'reciever': None, 'amount': None}
SWAP = {'type': 'swap', 'sender': None, 'amount': None, 'hash_lock': None, 'unix_expiration': None}
REDEEM = {'type': 'r', 'sender': None, 'secret': None}
STAMP = {'type': 'stamp', 'sender': None, 'amount': None}

TX_TYPES = [VOTE, STD, SWAP, REDEEM, STAMP]

JSON = {
    'payload': None,
    'proof': None,
    'signature': None
}


def is_valid_type(tx):
    return tx['payload']['type'] in [t['type'] for t in TX_TYPES]


def is_valid_fields(tx, type):
    pass

