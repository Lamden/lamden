from cilantro import Constants
from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.utils import validate_hex, int_to_decimal

import capnp
import transaction_capnp


class SwapTransaction(TransactionBase):

    name = "SWAPtomorrow_TX"

    @classmethod
    def deserialize_data(cls, data: bytes):
        return transaction_capnp.SwapTransaction.from_bytes_packed(data)

    def validate_payload(self):
        validate_hex(self.sender, 64, 'sender')
        validate_hex(self.receiver, 64, 'receiver')
        if self.amount <= 0:
            raise Exception("Amount must be greater than 0 (amount={})".format(self.amount))
        validate_hex(self.hashlock, 64, 'hashlock')

    @property
    def receiver(self):
        return self._data.payload.receiver.decode()

    @property
    def amount(self):
        return int_to_decimal(self._data.payload.amount)

    @property
    def hashlock(self):
        return self._data.payload.hashlock

    @property
    def expiration(self):
        return self._data.payload.expiration



class SwapTransactionBuilder:
    """
    This class provides utility methods for building transactions, and should only be used for testing.
    """

    @staticmethod
    def create_tx_struct(sender_s, sender_v, receiver, amount, hashlock, expiration):
        # Adjust amount for fixed point arithmetic
        amount *= pow(10, Constants.Protocol.DecimalPrecision)
        if type(amount) == float:
            amount = int(round(amount, 0))

        tx = transaction_capnp.SwapTransaction.new_message()

        tx.payload.sender = sender_v
        tx.payload.receiver = receiver
        tx.payload.amount = amount
        tx.payload.hashlock = hashlock
        tx.payload.expiration = expiration
        payload_binary = tx.payload.copy().to_bytes()

        tx.metadata.proof = Constants.Protocol.Proofs.find(payload_binary)[0]
        tx.metadata.signature = Constants.Protocol.Wallets.sign(sender_s, payload_binary)

        return tx

    @staticmethod
    def create_tx(sender_s, sender_v, receiver, amount, hashlock, expiration):
        tx_struct = SwapTransactionBuilder.create_tx_struct(sender_s, sender_v, receiver, amount, hashlock, expiration)
        return SwapTransaction.from_data(tx_struct)

    @staticmethod
    def random_tx():
        import random
        MULT = 1000
        import secrets

        import time

        tomorrow = int(time.time()) + (60 * 60 * 24)

        s = Constants.Protocol.Wallets.new()
        r = Constants.Protocol.Wallets.new()
        return SwapTransactionBuilder.create_tx(s[0], s[1], r[1], random.random() * MULT, secrets.token_bytes(64), tomorrow)