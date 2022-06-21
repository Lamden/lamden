from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, Driver, FSDriver
from lamden import storage, rewards
from lamden.contracts import sync
from lamden.logger.base import get_logger
import decimal
import gc
import json
import lamden
import legacy

import pathlib

log = get_logger('MIGRATE')

class MigrationNode:
    def __init__(self,
                 constitution=pathlib.Path.home().joinpath('constitution.json'),
                 debug=True, store=True, bypass_catchup=False,
                 genesis_path=lamden.contracts.__path__[0],
                 reward_manager=rewards.RewardManager(),
                 nonces=storage.NonceStorage()):

        self.new_blocks = storage.BlockStorage()
        self.old_blocks = legacy.BlockStorage()

        self.new_driver = ContractDriver()
        self.new_driver.driver = FSDriver()

        self.old_driver = ContractDriver()
        self.old_driver.driver = Driver()

        self.new_nonces = nonces
        self.store = store

        self.log = get_logger('MigrationNode')
        self.log.propagate = debug

        self.genesis_path = genesis_path

        self.client = ContractingClient(
            driver=self.new_driver,
            submission_filename=genesis_path + '/submission.s.py'
        )

        self.constitution = constitution

        self.reward_manager = reward_manager

        self.bypass_catchup = bypass_catchup

        with open(constitution) as f:
            self.constitution = json.load(f)

        self.seed_genesis_contracts()

    def seed_genesis_contracts(self):
        self.log.info('Setting up genesis contracts.')
        sync.setup_genesis_contracts(
            initial_masternodes=self.constitution['masternodes'],
            initial_delegates=self.constitution['delegates'],
            client=self.client,
            filename=self.genesis_path + '/genesis.json',
            root=self.genesis_path
        )

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
        self.new_driver.clear_pending_state()

        # Check if the block is valid
        if self.should_process(block):
            self.log.info('Storing new block.')
            # Commit the state changes and nonces to the database
            storage.update_state_with_block(
                block=block,
                driver=self.new_driver,
                nonces=self.new_nonces
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
            self.new_blocks.store_block(block)

        # Prepare for the next block by flushing out driver and notification state
        self.new_driver.commit()
        self.new_driver.clear_pending_state()
        gc.collect()

    def catchup(self):
        # Get the current latest block stored and the latest block of the network
        log.info('Running migration.')
        # Find the missing blocks process them
        while True:
            current = storage.get_latest_block_height(self.new_driver)
            latest = legacy.get_latest_block_height(self.old_driver)
            log.info(f'Current block: {current}, Latest available block: {latest}')
            # Increment current by one. Don't count the genesis block.
            current = 1 if current == 0 else current

            if current == latest:
                break

            for i in range(current, latest+1):
                block = self.old_blocks.get_block(v=i)
                log.info(f'Migrating block: #{i}')
                if block is not None:
                    self.process_new_block(block)

if __name__ == '__main__':
    mn = MigrationNode()
    mn.catchup()
