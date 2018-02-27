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


def is_valid_transaction_type(tx: dict) -> str:
    return tx['payload']['type'] in [t.type for t in TX_TYPES]


def is_valid_transaction_fields(tx: dict, _type: TransactionType) -> bool:
    return _type.is_transaction_type(tx)


def type_for_transaction(tx: dict) -> bool:
    assert is_valid_transaction_type(tx), 'Invalid transaction type passed'
    return tx['type']