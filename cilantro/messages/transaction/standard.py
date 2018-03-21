from cilantro import Constants
from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.utils import validate_hex, int_to_decimal

import capnp
import transaction_capnp


class StandardTransaction(TransactionBase):

    name = "STANDARD_TX"

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.StandardTransaction.from_bytes_packed(data)

    def validate_payload(self):
        validate_hex(self.sender, 64, 'sender')
        validate_hex(self.receiver, 64, 'receiver')
        if self.amount <= 0:
            raise Exception("Amount must be greater than 0 (amount={})".format(self.amount))

    @property
    def receiver(self):
        return self._data.payload.receiver.decode()

    @property
    def amount(self):
        return int_to_decimal(self._data.payload.amount)


class StandardTransactionBuilder:
    """
    This class provides utility methods for building transactions, and should only be used for testing.
    """

    @staticmethod
    def create_tx_struct(sender_s, sender_v, receiver, amount):
        # Adjust amount for fixed point arithmetic
        amount *= pow(10, Constants.Protocol.DecimalPrecision)
        if type(amount) == float:
            amount = int(round(amount, 0))

        tx = transaction_capnp.StandardTransaction.new_message()

        tx.payload.sender = sender_v
        tx.payload.receiver = receiver
        tx.payload.amount = amount
        payload_binary = tx.payload.copy().to_bytes()

        tx.metadata.proof = Constants.Protocol.Proofs.find(payload_binary)[0]
        tx.metadata.signature = Constants.Protocol.Wallets.sign(sender_s, payload_binary)

        return tx

    @staticmethod
    def create_tx(sender_s, sender_v, receiver, amount):
        tx_struct = StandardTransactionBuilder.create_tx_struct(sender_s, sender_v, receiver, amount)
        return StandardTransaction.from_data(tx_struct)

    @staticmethod
    def random_tx():
        import random
        MULT = 1000

        s = Constants.Protocol.Wallets.new()
        r = Constants.Protocol.Wallets.new()
        return StandardTransactionBuilder.create_tx(s[0], s[1], r[1], random.random() * MULT)