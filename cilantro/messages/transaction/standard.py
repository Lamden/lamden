from cilantro import Constants
from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.utils import validate_hex, int_to_decimal
from cilantro.protocol.wallet import Wallet
from cilantro.protocol.pow import SHA3POW
import capnp
import transaction_capnp


class StandardTransaction(TransactionBase):
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

    # TODO -- implement an agreeable fixed point solution
    @property
    def amount(self):
        return self._data.payload.amount


class StandardTransactionBuilder:
    """
    This class provides utility methods for building transactions, and should only be used for testing.
    """

    @staticmethod
    def create_tx_struct(sender_s, sender_v, receiver, amount):
        # Adjust amount for fixed point arithmetic
        # amount *= pow(10, Constants.Protocol.DecimalPrecision)
        # if type(amount) == float:
        #     amount = int(round(amount, 0))

        # Quick assertion for now since we dont support real number amounts
        assert type(amount) is int, "Transaction amount must be an integer (fixed point precision not yet supported)"


        tx = transaction_capnp.StandardTransaction.new_message()

        tx.payload.sender = sender_v
        tx.payload.receiver = receiver
        tx.payload.amount = amount
        payload_binary = tx.payload.copy().to_bytes()

        tx.metadata.proof = SHA3POW.find(payload_binary)[0]
        tx.metadata.signature = Wallet.sign(sender_s, payload_binary)

        return tx

    @staticmethod
    def create_tx(sender_s, sender_v, receiver, amount):
        tx_struct = StandardTransactionBuilder.create_tx_struct(sender_s, sender_v, receiver, amount)
        return StandardTransaction.from_data(tx_struct)

    @staticmethod
    def random_tx():
        import random
        MAX_AMT = 1000

        s = Wallet.new()
        r = Wallet.new()
        return StandardTransactionBuilder.create_tx(s[0], s[1], r[1], random.randint(1, MAX_AMT))
