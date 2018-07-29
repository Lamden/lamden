from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.utils import validate_hex, int_to_decimal
import time
from cilantro.protocol.wallet import Wallet
from cilantro.protocol.pow import SHA3POW
import capnp
import transaction_capnp


class SwapTransaction(TransactionBase):

    name = "SWAP_TX"

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.SwapTransaction.from_bytes_packed(data)

    def validate_payload(self):
        if self.amount <= 0:
            raise Exception("Amount must be greater than 0 (amount={})".format(self.amount))
        if len(self.hashlock) != 64:
            raise Exception("Hashlock incorrect length. Must be 64 bytes (length={})".format(len(self.hashlock)))
        if self.expiration < int(time.time()):
            raise Exception("Expiration date is before now.")

        validate_hex(self.receiver, length=64, field_name='Receiver')
        validate_hex(self.sender, length=64, field_name='Sender')


    @property
    def receiver(self):
        return self._data.payload.receiver.decode()

    @property
    def amount(self):
        return self._data.payload.amount

    @property
    def hashlock(self):
        return self._data.payload.hashlock.hex()

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
        # amount *= pow(10, Constants.Protocol.DecimalPrecision)
        # if type(amount) == float:
        #     amount = int(round(amount, 0))

        tx = transaction_capnp.SwapTransaction.new_message()

        tx.payload.sender = sender_v
        tx.payload.receiver = receiver
        tx.payload.amount = amount
        tx.payload.hashlock = hashlock
        tx.payload.expiration = expiration
        payload_binary = tx.payload.copy().to_bytes()

        tx.metadata.proof = SHA3POW.find(payload_binary)[0]
        tx.metadata.signature = Wallet.sign(sender_s, payload_binary)

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

        s = Wallet.new()
        r = Wallet.new()
        return SwapTransactionBuilder.create_tx(s[0], s[1], r[1], int(random.random() * MULT),
                                                secrets.token_hex(32), tomorrow)
