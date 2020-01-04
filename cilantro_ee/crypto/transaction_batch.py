from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.crypto import Wallet
import time
import hashlib


def transaction_list_to_transaction_batch(tx_list, wallet: Wallet):
    h = hashlib.sha3_256()
    for tx in tx_list:
        # Hash it
        tx_bytes = tx.to_bytes_packed()
        h.update(tx_bytes)
    # Add a timestamp
    timestamp = time.time()
    h.update('{}'.format(timestamp).encode())
    input_hash = h.digest()

    signature = wallet.sign(input_hash)

    msg = Message.get_message(
        msg_type=MessageType.TRANSACTION_BATCH,
        transactions=[t for t in tx_list],
        timestamp=timestamp,
        signature=signature,
        inputHash=input_hash,
        sender=wallet.verifying_key()
    )

    return msg[1]
