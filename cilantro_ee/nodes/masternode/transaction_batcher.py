from cilantro_ee.core.crypto.wallet import Wallet

from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType

from cilantro_ee.services.overlay.network import NetworkParameters
from cilantro_ee.services.storage.vkbook import VKBook

import hashlib
import time


class TransactionBatcher:
    def __init__(self,
                 wallet: Wallet,
                 queue):

        self.wallet = wallet
        self.queue = queue

    def pack_current_queue(self, tx_number=100):
        # Pop elements off into a list
        tx_list = []
        while len(tx_list) < tx_number or len(self.queue) > 0:
            tx_list.append(self.queue.pop(0))

        h = hashlib.sha3_256()
        for tx in tx_list:
            # Hash it
            tx_bytes = tx.as_builder().to_bytes_packed()
            h.update(tx_bytes)

        # Add a timestamp
        timestamp = time.time()
        h.update('{}'.format(timestamp).encode())
        inputHash = h.digest()

        # Sign the message for verification
        signature = self.wallet.sign(inputHash)

        msg = Message.get_signed_message_packed_2(
            wallet=self.wallet,
            msg_type=MessageType.TRANSACTION_BATCH,
            transactions=[t for t in tx_list], timestamp=timestamp,
            signature=signature, inputHash=inputHash,
            sender=self.wallet.verifying_key()
        )

        return msg
