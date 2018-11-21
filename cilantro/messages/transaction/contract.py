from cilantro.utils.lazy_property import lazy_property
from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.utils import validate_hex
from cilantro.protocol import wallet
from cilantro.utils import is_valid_hex
from cilantro.protocol.pow import SHA3POW
from decimal import *
import random
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
    build by some front end framework/library. Apart from the metadata, they contain one field called "code", which
    represents the code of the smart contract to be run, as plain text.
    """

    def validate_payload(self):
        validate_hex(self.sender, 64, 'sender')
        assert self.gas_supplied > 0, "Must supply positive gas amount u silly billy"
        assert is_valid_hex(self.nonce, 64), "Nonce {} not valid 64 char hex".format(self.nonce)

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.ContractTransaction.from_bytes_packed(data)

    @classmethod
    def create(cls, sender_sk: str, gas_supplied: int, contract_name: str,  func_name: str, nonce: str, *args, **kwargs):
        assert len(args) == 0, "Contract must be created with key word args only (no positional args sorry)"
        assert gas_supplied > 0, "Must supply positive gas amount u silly billy"
        assert is_valid_hex(nonce, 64), "Nonce {} not valid 64 char hex".format(nonce)

        struct = transaction_capnp.ContractTransaction.new_message()

        struct.payload.sender = wallet.get_vk(sender_sk)
        struct.payload.gasSupplied = gas_supplied
        struct.payload.contractName = contract_name
        struct.payload.functionName = func_name
        struct.payload.nonce = nonce

        struct.payload.kwargs.init('entries', len(kwargs))
        for i, key in enumerate(kwargs):
            struct.payload.kwargs.entries[i].key = key
            value, t = kwargs[key], type(kwargs[key])

            # Represent numeric types as strings so we do not lose any precision due to floating point
            if t in NUMERIC_TYPES:
                struct.payload.kwargs.entries[i].value.fixedPoint = str(value)
            else:
                assert t is not float, "Float types not allowed in kwargs. Used python's decimal.Decimal class instead"
                assert t in VALUE_TYPE_MAP, "value type {} with value {} not recognized in " \
                                            "types {}".format(t, kwargs[key], list(VALUE_TYPE_MAP.keys()))
                setattr(struct.payload.kwargs.entries[i].value, VALUE_TYPE_MAP[t], value)

        payload_binary = struct.payload.copy().to_bytes()

        struct.metadata.proof = SHA3POW.find(payload_binary)[0]
        struct.metadata.signature = wallet.sign(sender_sk, payload_binary)

        return ContractTransaction.from_data(struct)

    # @property
    @lazy_property
    def kwargs(self):
        d = {}
        for entry in self._data.payload.kwargs.entries:
            if entry.value.which() == 'fixedPoint':
                d[entry.key] = Decimal(entry.value.fixedPoint)
            else:
                d[entry.key] = getattr(entry.value, entry.value.which())

        return d

    @lazy_property
    def sender(self):
        return self._data.payload.sender.decode()

    @property
    def nonce(self):
        return self._data.payload.nonce

    @property
    def contract_name(self):
        return self._data.payload.contractName

    @property
    def func_name(self):
        return self._data.payload.functionName

    @property
    def gas_supplied(self):
        return self._data.payload.gasSupplied


class ContractTransactionBuilder:
    """
    Utility methods to construct ContractTransactions. We use this exclusively for testing, as IRL this should be done by
    users via some JS library or something.
    """
    CURRENCY_CONTRACT_NAME = 'kv_currency'

    @staticmethod
    def create_currency_tx(sender_sk: str, receiver_vk: str, amount: Union[int, Decimal], gas=1000):
        return ContractTransaction.create(sender_sk=sender_sk, gas_supplied=gas,
                                          contract_name=ContractTransactionBuilder.CURRENCY_CONTRACT_NAME,
                                          func_name='transfer', nonce='A' * 64, to=receiver_vk, amount=amount)

    @staticmethod
    def random_currency_tx():
        from cilantro.utils.test.god import ALL_WALLETS
        import random

        sender, receiver = random.sample(ALL_WALLETS, 2)
        amount = random.randint(1, 2 ** 8)
        return ContractTransactionBuilder.create_currency_tx(sender[0], receiver[1], amount)

    # @staticmethod
    # def create_dummy_tx(sender_sk: str, receiver_vk: str, fail: bool):
    #
    #     code_str = ContractTemplate.interpolate_template('dummy', fail=fail)
    #     return ContractTransactionBuilder.create_contract_tx(sender_sk, code_str)
