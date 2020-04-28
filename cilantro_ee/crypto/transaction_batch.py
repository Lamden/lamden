from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.crypto.wallet import Wallet, _verify
import hashlib
from .transaction import transaction_is_valid, TransactionException
import time


class TransactionBatchProcessingException(Exception):
    pass


class NotTransactionBatchMessageType(TransactionBatchProcessingException):
    pass


class ReceivedInvalidWork(TransactionBatchProcessingException):
    pass


class InvalidSignature(TransactionBatchProcessingException):
    pass


class TransactionBatchNotFromMasternode(TransactionBatchProcessingException):
    pass


# Capnp for now. JSON later?
def transaction_batch_is_valid(tx_batch, current_masternodes, driver):
    if tx_batch.sender.hex() not in current_masternodes:
        print(current_masternodes)
        raise TransactionBatchNotFromMasternode

    # Set up a hasher for input hash and a list for valid txs
    h = hashlib.sha3_256()

    for tx in tx_batch.transactions:
        # Double check to make sure all transactions are valid
        try:
            transaction_is_valid(tx=tx,
                                 expected_processor=tx_batch.sender,
                                 driver=driver,
                                 strict=False)
        except TransactionException as e:
            raise e

        h.update(tx.as_builder().to_bytes_packed())

    h.update('{}'.format(tx_batch.timestamp).encode())
    input_hash = h.digest().hex()
    if input_hash != tx_batch.inputHash or \
            not _verify(tx_batch.sender, h.digest(), tx_batch.signature):
        raise InvalidSignature


def transaction_list_to_transaction_batch(tx_list, wallet: Wallet):
    h = hashlib.sha3_256()
    for tx in tx_list:
        # Hash it
        tx_bytes = tx.to_bytes_packed()
        h.update(tx_bytes)
    # Add a timestamp
    timestamp = time.time()
    h.update('{}'.format(timestamp).encode())
    input_hash = h.digest().hex()

    signature = wallet.sign(bytes.fromhex(input_hash))

    msg = Message.get_message(
        msg_type=MessageType.TRANSACTION_BATCH,
        transactions=[t for t in tx_list],
        timestamp=timestamp,
        signature=signature,
        inputHash=input_hash,
        sender=wallet.verifying_key()
    )

    return msg[1]
