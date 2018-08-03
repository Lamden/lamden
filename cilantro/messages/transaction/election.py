from cilantro.messages.transaction.base import TransactionBase
from cilantro.protocol import wallet
from cilantro.protocol.pow import SHA3POW
import capnp
import transaction_capnp

from cilantro.messages.utils import validate_hex


class ElectionTransaction(TransactionBase):
    name = "ELECTION_TX"

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.VoteTransaction.from_bytes_packed(data)

    def validate_payload(self):
        validate_hex(self.sender, 64, 'sender')
        validate_hex(self.policy, None, 'policy')

    @property
    def policy(self):
        return self._data.payload.policy.decode()

    @property
    def method(self):
        return self._data.payload.method


class ElectionTransactionBuilder:
    """
    This class provides utility methods for building transactions, and should only be used for testing.
    """

    @staticmethod
    def create_tx_struct(sender_s, sender_v, policy, method):
        tx = transaction_capnp.VoteTransaction.new_message()

        tx.payload.sender = sender_v
        tx.payload.policy = policy
        tx.payload.method = method
        payload_binary = tx.payload.copy().to_bytes()

        tx.metadata.proof = SHA3POW.find(payload_binary)[0]
        tx.metadata.signature = wallet.sign(sender_s, payload_binary)

        return tx

    @staticmethod
    def create_tx(sender_s, sender_v, policy, method):
        tx_struct = ElectionTransactionBuilder.create_tx_struct(sender_s, sender_v, policy, method)
        return ElectionTransaction.from_data(tx_struct)

    @staticmethod
    def random_tx():
        import secrets
        import random

        method = 0 if random.random() > 0.5 else 1

        s = wallet.new()
        return ElectionTransactionBuilder.create_tx(s[0], s[1], secrets.token_hex(8), method)
