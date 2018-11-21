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


class PublishTransaction(TransactionBase):
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
        return transaction_capnp.PublishTransaction.from_bytes_packed(data)

    @classmethod
    def create(cls, sender_sk: str, gas_supplied: int, contract_name: str,  contract_code: str, nonce: str, *args, **kwargs):
        assert len(args) == 0, "Contract must be created with key word args only (no positional args sorry)"
        assert gas_supplied > 0, "Must supply positive gas amount u silly billy"
        assert is_valid_hex(nonce, 64), "Nonce {} not valid 64 char hex".format(nonce)

        struct = transaction_capnp.PublishTransaction.new_message()

        struct.payload.sender = wallet.get_vk(sender_sk)
        struct.payload.gasSupplied = gas_supplied
        struct.payload.contractName = contract_name
        struct.payload.contractCode = contract_code
        struct.payload.nonce = nonce

        payload_binary = struct.payload.copy().to_bytes()

        struct.metadata.proof = SHA3POW.find(payload_binary)[0]
        struct.metadata.signature = wallet.sign(sender_sk, payload_binary)

        return PublishTransaction.from_data(struct)

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

    @property
    def contract_code(self):
        return self._data.payload.contractCode


