from cilantro.messages.transaction.base import TransactionBase
from cilantro.protocol import wallet
from cilantro.utils import is_valid_hex
from cilantro.protocol.pow import SHA3POW
from decimal import *
import random
from typing import Union

import capnp
import transaction_capnp


# TODO lot of repetition with this class and ContractTransaction. Can likely abstract much out of it

class PublishTransaction(TransactionBase):

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.PublishTransaction.from_bytes_packed(data)

    @classmethod
    def create(cls, sender_sk: str, gas_supplied: int, contract_name: str,  contract_code: str, nonce: str, *args, **kwargs):
        assert len(args) == 0, "Contract must be created with key word args only (no positional args sorry)"
        assert gas_supplied > 0, "Must supply positive gas amount u silly billy"

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

    @property
    def contract_name(self):
        return self._data.payload.contractName

    @property
    def contract_code(self):
        return self._data.payload.contractCode


