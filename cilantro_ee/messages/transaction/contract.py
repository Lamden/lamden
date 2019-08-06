from cilantro_ee.utils.lazy_property import lazy_property
from cilantro_ee.messages.transaction.base import TransactionBase
from cilantro_ee.messages.utils import validate_hex
from cilantro_ee.protocol import wallet
from cilantro_ee.utils import is_valid_hex
from cilantro_ee.protocol.pow import SHA3POW
from decimal import *
import random, secrets
from typing import Union

import capnp
import transaction_capnp


NUMERIC_TYPES = {int, Decimal}
VALUE_TYPE_MAP = {
    str: 'text',
    bytes: 'data',
    bool: 'bool'
}


class ContractTransaction(TransactionBase):
    """
    ContractTransactions are sent into the system by users who wish to execute smart contracts. IRL, they should be
    build by some front end framework/library.
    """

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.ContractTransaction.from_bytes_packed(data)

    @classmethod
    def _deserialize_payload(cls, data: bytes):
        return transaction_capnp.TransactionPayload.from_bytes(data)

    @classmethod
    def create(cls, sender_sk: str, stamps_supplied: int, processor: bytes, contract_name: str, func_name: str, nonce: str, kwargs: dict):
        # assert stamps_supplied > 0, "Must supply positive stamps amount"

        if not nonce:
            nonce = wallet.get_vk(sender_sk) + ":" + secrets.token_bytes(32).hex()

        struct = transaction_capnp.ContractTransaction.new_message()
        payload = transaction_capnp.TransactionPayload.new_message()

        payload.sender = wallet.get_vk(sender_sk)
        payload.stampsSupplied = stamps_supplied
        payload.processor = processor
        payload.contractName = contract_name
        payload.functionName = func_name
        payload.nonce = nonce

        payload.kwargs.init('entries', len(kwargs))
        for i, key in enumerate(kwargs):
            payload.kwargs.entries[i].key = key
            value, t = kwargs[key], type(kwargs[key])

            # Represent numeric types as strings so we do not lose any precision due to floating point
            if t in NUMERIC_TYPES:
                payload.kwargs.entries[i].value.fixedPoint = str(value)
            else:
                assert t is not float, "Float types not allowed in kwargs. Used python's decimal.Decimal class instead"
                assert t in VALUE_TYPE_MAP, "value type {} with value {} not recognized in " \
                                            "types {}".format(t, kwargs[key], list(VALUE_TYPE_MAP.keys()))
                setattr(payload.kwargs.entries[i].value, VALUE_TYPE_MAP[t], value)

        payload_binary = payload.to_bytes()

        struct.metadata.proof = SHA3POW.find(payload_binary)[0]  # Nah
        struct.metadata.signature = wallet.sign(sender_sk, payload_binary)  # Nah
        struct.payload = payload_binary

        return ContractTransaction.from_data(struct)

    # @property
    @lazy_property
    def kwargs(self):
        d = {}
        for entry in self.payload.kwargs.entries:
            if entry.value.which() == 'fixedPoint':
                d[entry.key] = Decimal(entry.value.fixedPoint)
            else:
                d[entry.key] = getattr(entry.value, entry.value.which())

        return d

    @property
    def contract_name(self):
        return self.payload.contractName

    @property
    def func_name(self):
        return self.payload.functionName


class ContractTransactionBuilder:
    """
    Utility methods to construct ContractTransactions. We use this exclusively for testing, as IRL this should be done by
    users via some JS library or something.
    """
    CURRENCY_CONTRACT_NAME = 'currency'

    @staticmethod
    def create_currency_tx(sender_sk: str, receiver_vk: str, amount: Union[int, Decimal], stamps=1000000, nonce=None):
        vk = wallet.get_vk(sender_sk)
        nonce = nonce or "{}:{}".format(vk, 'A' * 64)

        return ContractTransaction.create(sender_sk=sender_sk, stamps_supplied=stamps,
                                          contract_name=ContractTransactionBuilder.CURRENCY_CONTRACT_NAME,
                                          func_name='transfer', nonce=nonce, kwargs={'to':receiver_vk, 'amount':amount})

    @staticmethod
    def random_currency_tx():
        from cilantro_ee.utils.test.god import ALL_WALLETS
        import random

        sender, receiver = random.sample(ALL_WALLETS, 2)
        amount = random.randint(1, 2 ** 8)
        return ContractTransactionBuilder.create_currency_tx(sender[0], receiver[1], amount)
