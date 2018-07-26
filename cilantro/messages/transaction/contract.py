from cilantro import Constants
from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.utils import validate_hex
from cilantro.protocol.wallets import ED25519Wallet

import capnp
import transaction_capnp
import time

class ContractTransaction(TransactionBase):
    """
    ContractTransactions are sent into the system by users who wish to execute smart contracts. IRL, they should be
    build by some front end framework/library. Apart from the metadata, they contain one field called "code", which
    represents the code of the smart contract to be run, as plain text.
    """

    def validate_payload(self):
        validate_hex(self.sender, 64, 'sender')

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.ContractTransaction.from_bytes_packed(data)

    @property
    def code(self):
        return self._data.payload.code

class ContractTransactionBuilder:
    """
    Utility methods to construct ContractTransactions. We use this exclusively for testing, as IRL this should be done by
    users via some JS library or something.
    """
    @staticmethod
    def create_contract_tx(sender_sk: str, code_str: str):
        validate_hex(sender_sk, 64, 'sender signing key')

        struct = transaction_capnp.ContractTransaction.new_message()

        struct.payload.sender = ED25519Wallet.get_vk(sender_sk)
        struct.payload.code = code_str

        payload_binary = struct.payload.copy().to_bytes()

        struct.metadata.proof = Constants.Protocol.Proofs.find(payload_binary)[0]
        struct.metadata.signature = ED25519Wallet.sign(sender_sk, payload_binary)

        return ContractTransaction.from_data(struct)

    @staticmethod
    def create_currency_tx(sender_sk: str, receiver_vk: str, amount: int):
        from cilantro.db.templating import ContractTemplate

        validate_hex(receiver_vk, 64, 'receiver verifying key')
        code_str = ContractTemplate.interpolate_template('currency', amount=amount, receiver=receiver_vk)
        return ContractTransactionBuilder.create_contract_tx(sender_sk, code_str)

    @staticmethod
    def create_dummy_tx(sender_sk: str, receiver_vk: str, fail: bool):
        from cilantro.db.templating import ContractTemplate

        code_str = ContractTemplate.interpolate_template('dummy', fail=fail)
        return ContractTransactionBuilder.create_contract_tx(sender_sk, code_str)
