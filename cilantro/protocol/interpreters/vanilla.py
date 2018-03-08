from .base import TransactionType


class VanillaInterpreter:
    VOTE = 'VOTE'
    STD = 'STD'
    SWAP = 'SWAP'
    REDEEM = 'REDEEM'
    STAMP = 'STAMP'

    vote_tx = TransactionType(VOTE, ['sender', 'key', 'value'])
    standard_tx = TransactionType(STD, ['sender', 'receiver', 'amount'])
    swap_tx = TransactionType(SWAP, ['sender', 'amount', 'hash_lock', 'unix_expiration'])
    redeem_tx = TransactionType(REDEEM, ['sender', 'secret'])
    stamp_tx = TransactionType(STAMP, ['sender', 'amount'])

    TX_TYPES = [vote_tx,
                standard_tx,
                swap_tx,
                redeem_tx,
                stamp_tx]

    @classmethod
    def is_valid(cls, tx:dict) -> bool:
        return tx['payload']['type'] in [t.type for t in cls.TX_TYPES] and \
               tx['payload']['type'].is_transaction_type(tx)