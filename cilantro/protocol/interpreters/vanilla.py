from .base import TransactionType

vote_tx = TransactionType('VOTE', ['sender', 'key', 'value'])
standard_tx = TransactionType('STD', ['sender', 'receiver', 'amount'])
swap_tx = TransactionType('SWAP', ['sender', 'amount', 'hash_lock', 'unix_expiration'])
redeem_tx = TransactionType('REDEEM', ['sender', 'secret'])
stamp_tx = TransactionType('STAMP', ['sender', 'amount'])

TX_TYPES = [vote_tx,
            standard_tx,
            swap_tx,
            redeem_tx,
            stamp_tx]

def is_valid_transaction_type(tx):
    return tx['payload']['type'] in [t.type for t in TX_TYPES]


def is_valid_transaction_fields(tx, type):
    pass