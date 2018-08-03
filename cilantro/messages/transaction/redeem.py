from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.utils import validate_hex, int_to_decimal
from cilantro.protocol import wallet
from cilantro.protocol.pow import SHA3POW
import capnp
import transaction_capnp


class RedeemTransaction(TransactionBase):

    name = "REDEEM_TX"

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.RedeemTransaction.from_bytes_packed(data)

    def validate_payload(self):
        validate_hex(self.sender, 64, 'sender')

    @property
    def secret(self):
        return self._data.payload.secret.decode()


class RedeemTransactionBuilder:
    """
    This class provides utility methods for building transactions, and should only be used for testing.
    """

    @staticmethod
    def create_tx_struct(sender_s, sender_v, secret):
        # Adjust amount for fixed point arithmetic
        tx = transaction_capnp.RedeemTransaction.new_message()

        tx.payload.sender = sender_v
        tx.payload.secret = secret
        payload_binary = tx.payload.copy().to_bytes()

        tx.metadata.proof = SHA3POW.find(payload_binary)[0]
        tx.metadata.signature = wallet.sign(sender_s, payload_binary)

        return tx

    @staticmethod
    def create_tx(sender_s, sender_v, secret):
        tx_struct = RedeemTransactionBuilder.create_tx_struct(sender_s, sender_v, secret)
        return RedeemTransaction.from_data(tx_struct)

    @staticmethod
    def random_tx():
        import secrets

        s = wallet.new()
        return RedeemTransactionBuilder.create_tx(s[0], s[1], secrets.token_hex(32))
