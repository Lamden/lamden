from unittest import TestCase
from lamden.nodes import work
from lamden.nodes.hlc import HLC_Clock
from lamden.crypto.wallet import Wallet
from lamden.crypto import transaction
import hashlib
import time
import asyncio

wallet = Wallet()
hlc_clock = HLC_Clock()

def get_masters():
    return [wallet.verifying_key]

def make_tx():
    tx = transaction.build_transaction(
        wallet=wallet,
        processor='b' * 64,
        nonce=0,
        contract='currency',
        function='transfer',
        kwargs={
            'amount': 123,
            'to': 'jeff'
        },
        stamps=0
    )

    timestamp = int(time.time())

    h = hashlib.sha3_256()
    h.update('{}'.format(timestamp).encode())
    input_hash = h.hexdigest()

    signature = wallet.sign(input_hash)

    return {
        'tx': tx,
        'timestamp': timestamp,
        'hlc_timestamp': hlc_clock.get_new_hlc_timestamp(),
        'signature': signature,
        'sender': wallet.verifying_key,
        'input_hash': input_hash
    }


mock_tx = make_tx()

class TestWorkValidator(TestCase):
    def test_init_work_validator(self):
        main_processing_queue = []
        work.WorkValidator(
            wallet=wallet,
            add_to_main_processing_queue=lambda x: main_processing_queue.append(x),
            hlc_clock=hlc_clock,
            get_masters=get_masters
        )

    def test_process_message(self):
        print(hlc_clock.get_new_hlc_timestamp())
        main_processing_queue = []
        work_validator = work.WorkValidator(
            wallet=wallet,
            add_to_main_processing_queue=lambda x: main_processing_queue.append(x),
            hlc_clock=hlc_clock,
            get_masters=get_masters
        )

        async def receive_message():
            await work_validator.process_message(mock_tx)

        tasks = asyncio.gather(
            receive_message()
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(len(main_processing_queue), 1)

