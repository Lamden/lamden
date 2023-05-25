from unittest import TestCase
from pathlib import Path
from datetime import datetime as dt

import os
import shutil
import math
import hashlib
import marshal

from contracting.db.driver import FSDriver, ContractDriver
from contracting.client import ContractingClient
from contracting.execution.executor import Executor
from contracting.db.encoder import convert_dict
from contracting.stdlib.bridge.time import Datetime

from lamden.nodes.hlc import HLC_Clock
from lamden.contracts import sync
from lamden.crypto.wallet import Wallet


CODE_KEY = '__code__'
COMPILED_KEY = '__compiled__'


class TestMemberVoting(TestCase):
    def setUp(self):
        self.root = './.lamden'
        self.create_directories()

        self.storage_driver = FSDriver(root=self.root)
        self.contract_driver = ContractDriver(driver=self.storage_driver)
        self.client = ContractingClient(
            driver=self.contract_driver,
            submission_filename='./helpers/submission.py'
        )
        self.executor = Executor(driver=self.contract_driver, metering=False)
        self.hlc_clock = HLC_Clock()

        self.jeff = Wallet()
        self.stu = Wallet()
        self.oliver = Wallet()

        self.initial_members = [
            self.jeff.verifying_key, self.stu.verifying_key, self.oliver.verifying_key
        ]

        with open(sync.DEFAULT_PATH + '/genesis/election_house.s.py') as f:
            contract = f.read()

        self.client.submit(contract, name='election_house')
        self.driver_commit()

        with open(sync.DEFAULT_PATH + '/genesis/members.s.py') as f:
            contract = f.read()

        self.client.submit(contract, name='masternodes', owner='election_house', constructor_args={
            'initial_members': self.initial_members
        })
        self.driver_commit()

        election_house = self.client.get_contract('election_house')
        election_house.register_policy(contract='masternodes')


    def tearDown(self):
        pass

    def create_directories(self):
        if os.path.exists(Path(self.root)):
            shutil.rmtree(Path(self.root))

        os.makedirs(Path(self.root))

    def get_now_from_nanos(self, add_time: int = 0):
        current_hlc_timestamp = self.hlc_clock.get_new_hlc_timestamp()
        nanos = self.hlc_clock.get_nanos(current_hlc_timestamp)
        nanos = nanos + add_time
        return Datetime._from_datetime(
            dt.utcfromtimestamp(math.ceil(nanos / 1e9))
        )

    def get_nanos_hash(self, nanos):
        h = hashlib.sha3_256()
        h.update('{}'.format(nanos).encode())
        return h.hexdigest()

    def set_contract_code(self):
        with open(sync.DEFAULT_PATH + '/genesis/members.s.py') as f:
            code = f.read()

        code_obj = compile(code, '', 'exec')
        code_blob = marshal.dumps(code_obj)

        self.contract_driver.set_var('masternodes', CODE_KEY, value=code)
        self.contract_driver.set_var('masternodes', COMPILED_KEY, value=code_blob)

    def set_masternode_state(self, variable='S', arguments=[], value=None):
        if value is None:
            raise ValueError("Must set a value")
        self.client.raw_driver.set_var('masternodes', variable, arguments=arguments, value=value)

    def driver_commit(self):
        hlc_timestamp = self.hlc_clock.get_new_hlc_timestamp()
        self.contract_driver.soft_apply(hcl=hlc_timestamp)
        self.contract_driver.hard_apply_one(hlc=hlc_timestamp)
        self.contract_driver.commit()

    def test_new_vote_can_reset_state_after_motion_expires(self):
        current_hlc = self.hlc_clock.get_new_hlc_timestamp()
        stamp_cost = self.client.get_var(contract='stamp_cost', variable='S', arguments=['value'])

        nanos = self.hlc_clock.get_nanos(timestamp=current_hlc)

        environment = {
            'block_hash': self.get_nanos_hash(nanos=nanos),  # hash nanos
            'block_num': nanos,  # hlc to nanos
            '__input_hash': 64 * '0',  # Used for deterministic entropy for random games
            'now': self.get_now_from_nanos(),
            'AUXILIARY_SALT': 128 * '0'
        }

        transaction = {
            'payload': {
                'sender': self.oliver.verifying_key,
                'contract': 'election_house',
                'function': 'vote',
                'stamps_supplied': 1000,
                'kwargs': {
                    'policy': 'masternodes',
                    'value': [
                        'vote_on_motion',
                        True
                    ]
                },
            }
        }

        self.set_masternode_state(arguments=['current_motion'], value=1)
        self.set_masternode_state(arguments=['member_in_question'], value=self.jeff.verifying_key)
        self.set_masternode_state(arguments=['positions', self.stu.verifying_key], value=True)
        self.set_masternode_state(arguments=['yays'], value=1)
        self.set_masternode_state(arguments=['motion_opened'], value=Datetime(year=2019, month=1, day=1))

        self.driver_commit()

        output = self.executor.execute(
            sender=transaction['payload']['sender'],
            contract_name=transaction['payload']['contract'],
            function_name=transaction['payload']['function'],
            stamps=transaction['payload']['stamps_supplied'],
            stamp_cost=stamp_cost,
            kwargs=convert_dict(transaction['payload']['kwargs']),
            environment=environment,
            auto_commit=False
        )

        self.assertEqual(output.get('status_code'), 0)

        writes = output.get('writes')
        self.assertEqual(0, writes.get('masternodes.S:current_motion'))
        self.assertEqual(None, writes.get(f'masternodes.S:positions:{self.stu.verifying_key}'))
        self.assertEqual(None, writes.get(f'masternodes.S:positions:{self.jeff.verifying_key}'))

        # This sucks because the contract will get reset but also a vote will be cast.
        # The Developer didn't put a "return" after the reset() call when the motion expired.
        self.assertEqual(True, writes.get(f'masternodes.S:positions:{self.oliver.verifying_key}'))