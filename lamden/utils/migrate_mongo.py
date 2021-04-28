from . import legacy

from lamden import storage, rewards
from lamden.contracts import sync
from contracting.db.driver import ContractDriver, encode, Driver, FSDriver
import lamden
import json
from contracting.client import ContractingClient
import gc
from lamden.logger.base import get_logger
import decimal

import pathlib

log = get_logger('MIGRATE')


class MigrationNode:
    def __init__(self,
                 constitution=pathlib.Path.home().joinpath('constitution.json'),
                 debug=True, store=True, seed=None, bypass_catchup=False,
                 genesis_path=lamden.contracts.__path__[0],
                 reward_manager=rewards.RewardManager(),
                 nonces=storage.NonceStorage()):

        self.new_blocks = storage.BlockStorage()
        self.old_blocks = legacy.LegacyBlockStorage()

        self.blocks = self.new_blocks

        # Has the new FSDriver
        self.new_driver = ContractDriver()
        self.new_driver.driver = FSDriver()

        # Does not have the new FSDriver
        self.old_driver = ContractDriver()
        self.old_driver.driver = Driver()

        self.driver = self.new_driver
        self.nonces = nonces
        self.store = store

        self.seed = seed

        self.log = get_logger('Base')
        self.log.propagate = debug

        self.genesis_path = genesis_path

        self.client = ContractingClient(
            driver=self.driver,
            submission_filename=genesis_path + '/submission.s.py'
        )

        self.constitution = constitution

        self.reward_manager = reward_manager

        self.bypass_catchup = bypass_catchup

        with open(constitution) as f:
            self.constitution = json.load(f)

    def seed_genesis_contracts(self):
        self.log.info('Setting up genesis contracts.')
        sync.setup_genesis_contracts(
            initial_masternodes=self.constitution['masternodes'],
            initial_delegates=self.constitution['delegates'],
            client=self.client,
            filename=self.genesis_path + '/genesis.json',
            root=self.genesis_path
        )

    def catchup(self, current=0):
        # Get the current latest block stored and the latest block of the network
        log.info('Running migration.')

        latest = legacy.get_latest_block_height(self.old_driver)

        log.info(f'Current block: {current}, Latest available block: {latest}')

        # Increment current by one. Don't count the genesis block.
        if current == 0:
            current = 1

        # Find the missing blocks process them
        for i in range(current, latest + 1):
            block = None
            while block is None:
                block = self.old_blocks.get_block(v=i)

            self.process_new_block(block)

    def should_process(self, block):
        try:
            self.log.info(f'Processing block #{block.get("number")}')
        except:
            self.log.error('Malformed block :(')
            return False
        # Test if block failed immediately
        if block == {'response': 'ok'}:
            return False

        if block['hash'] == 'f' * 64:
            self.log.error('Failed Block! Not storing.')
            return False

        return True

    def update_state(self, block):
        self.driver.clear_pending_state()

        # Check if the block is valid
        if self.should_process(block):
            self.log.info('Storing new block.')
            # Commit the state changes and nonces to the database
            storage.update_state_with_block(
                block=block,
                driver=self.driver,
                nonces=self.nonces
            )

            self.log.info('Issuing rewards.')
            # Calculate and issue the rewards for the governance nodes
            self.reward_manager.issue_rewards(
                block=block,
                client=self.client
            )

        self.log.info('Updating metadata.')

    def process_new_block(self, block):
        # Update the state and refresh the sockets so new nodes can join
        self.update_state(block)

        # Store the block if it's a masternode
        if self.store:
            encoded_block = encode(block)
            encoded_block = json.loads(encoded_block, parse_int=decimal.Decimal)

            self.blocks.store_block(encoded_block)

        # Prepare for the next block by flushing out driver and notification state

        # Finally, check and initiate an upgrade if one needs to be done
        self.driver.commit()
        self.driver.clear_pending_state()
        gc.collect()
