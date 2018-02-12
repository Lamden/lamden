from cilantro.proofs.pow import SHA3POW
from cilantro.wallets import ED25519Wallet
from cilantro.transactions.core import Transaction

class BaseInterpreter(object):
    """
    Abstract base class for interpreter implementations. This class should never be instantiated, but rather should be
    subclassed by all interpreter implementations.
    """

    def __init__(self, wallet=ED25519Wallet, proof_system=SHA3POW):
        self.wallet = wallet
        self.proof_system = proof_system

    def interpret_transaction(self, transaction: Transaction):
        """
        Interprets the transaction, and updates scratch/balance state as necessary.
        If any validation fails (i.e. insufficient balance), this method will throw an error

        :param transaction: A Transaction object to interpret
        """
        raise NotImplementedError