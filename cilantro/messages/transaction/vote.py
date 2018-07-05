from cilantro.messages.transaction.base import TransactionBase
from cilantro import Constants

import capnp
import transaction_capnp

from cilantro.messages.utils import validate_hex


class VoteTransaction(TransactionBase):
    name = "VOTE_TX"

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.VoteTransaction.from_bytes_packed(data)

    def validate_payload(self):
        validate_hex(self.sender, 64, 'sender')
        validate_hex(self.policy, None, 'policy')
        validate_hex(self.choice, None, 'choice')

    @property
    def policy(self):
        return self._data.payload.policy.decode()

    @property
    def choice(self):
        return self._data.payload.choice.decode()


class VoteTransactionBuilder:
    """
    This class provides utility methods for building transactions, and should only be used for testing.
    """

    @staticmethod
    def create_tx_struct(sender_s, sender_v, policy, choice):
        tx = transaction_capnp.VoteTransaction.new_message()

        tx.payload.sender = sender_v
        tx.payload.policy = policy
        tx.payload.choice = choice
        payload_binary = tx.payload.copy().to_bytes()

        tx.metadata.proof = Constants.Protocol.Proofs.find(payload_binary)[0]
        tx.metadata.signature = Constants.Protocol.Wallets.sign(sender_s, payload_binary)

        return tx

    @staticmethod
    def create_tx(sender_s, sender_v, policy, choice):
        tx_struct = VoteTransactionBuilder.create_tx_struct(sender_s, sender_v, policy, choice)
        return VoteTransaction.from_data(tx_struct)

    @staticmethod
    def random_tx():
        import secrets

        s = Constants.Protocol.Wallets.new()
        return VoteTransactionBuilder.create_tx(s[0], s[1], secrets.token_hex(8), secrets.token_hex(8))
