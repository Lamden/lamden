from cilantro import Constants
from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.utils import validate_hex, int_to_decimal
from cilantro.protocol.wallet import Wallet
import capnp
import transaction_capnp


class StampTransaction(TransactionBase):

    name = "REDEEM_TX"

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.RedeemTransaction.from_bytes_packed(data)

    def validate_payload(self):
        validate_hex(self.sender, 64, 'sender')

    @property
    def amount(self):
        return self._data.payload.amount


class StampTransactionBuilder:
    """
    This class provides utility methods for building transactions, and should only be used for testing.
    """

    @staticmethod
    def create_tx_struct(sender_s, sender_v, amount):
        # Adjust amount for fixed point arithmetic
        tx = transaction_capnp.RedeemTransaction.new_message()

        tx.payload.sender = sender_v
        tx.payload.secret = amount
        payload_binary = tx.payload.copy().to_bytes()

        tx.metadata.proof = Constants.Protocol.Proofs.find(payload_binary)[0]
        tx.metadata.signature = Wallet.sign(sender_s, payload_binary)

        return tx

    @staticmethod
    def create_tx(sender_s, sender_v, amount):
        tx_struct = StampTransactionBuilder.create_tx_struct(sender_s, sender_v, amount)
        return StampTransaction.from_data(tx_struct)

    @staticmethod
    def random_tx():
        import random
        MULT = 1000
        negative = True if random.random() > 0.5 else False

        amount = int(random.random() * MULT)
        if negative:
            amount *= -1

        s = Wallet.new()
        r = Wallet.new()
        return StampTransactionBuilder.create_tx(s[0], s[1], r[1], amount)