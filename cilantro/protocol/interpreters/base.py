from cilantro import Constants
from cilantro.messages import TransactionBase

class BaseInterpreter(object):
    """
    Abstract base class for interpreter implementations. This class should never be instantiated, but rather should be
    subclassed by all interpreter implementations.
    """

    def __init__(self, wallet=Constants.Protocol.Wallets, proof_system=Constants.Protocol.Proofs):
        self.wallet = wallet
        self.proof_system = proof_system

    def interpret_transaction(self, transaction: TransactionBase):
        """
        Interprets the transaction, and updates scratch/balance state as necessary.
        If any validation fails (i.e. insufficient balance), this method will throw an error
        :param transaction: A Transaction object to interpret
        """
        raise NotImplementedError

# class TransactionType:
#     def __init__(self, _type, keys):
#         keys.append('type')
#         self.repr = dict([(k, None) for k in keys])
#         self.repr['type'] = _type
#         self.type = self.repr['type']
#
#     def is_transaction_type(self, tx):
#         return tx.keys() == self.repr.keys() and tx['type'] == self.repr['type']
