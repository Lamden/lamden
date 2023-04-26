from lamden.utils.migrate_blocks_dir import MigrateFiles
from lamden.storage import FSBlockDriver

import os
import shutil
from pathlib import Path
from unittest import TestCase
import random
import time
import json
import hashlib


class TestMigrateBlocksDir(TestCase):
    def setUp(self):
        self.test_dir = './.lamden'
        self.blocks_dir = 'blocks'
        self.alias_dir = 'alias'
        self.txs_dir = 'txs'

        self.blocks_dest_dir = 'migrated'
        self.block_alias_dir = 'block_alias'

        self.blocks_path = os.path.join(self.test_dir, self.blocks_dir)
        self.blocks_dest_path = os.path.join(self.test_dir, self.blocks_dest_dir)

        self.alias_path = os.path.join(self.test_dir, self.blocks_dir, self.alias_dir)
        self.alias_path_dest = os.path.join(self.test_dir, self.block_alias_dir)

        self.txs_path = os.path.join(self.test_dir, self.blocks_dir,  self.txs_dir)
        self.txs_path_dest = os.path.join(self.test_dir, self.txs_dir)

        self.create_directories()
        self.block_driver = FSBlockDriver(root=self.blocks_dest_path)


    def tearDown(self):
        pass

    def create_directories(self):
        if os.path.exists(Path(self.test_dir)):
            shutil.rmtree(Path(self.test_dir))

        os.makedirs(Path(self.test_dir))
        os.makedirs(self.blocks_path)
        os.makedirs(self.blocks_dest_path)

        os.makedirs(self.alias_path)
        os.makedirs(self.alias_path_dest)

        os.makedirs(self.txs_path)
        os.makedirs(self.txs_path_dest)


    def create_hash(self, data: str):
        h = hashlib.sha3_256()
        h.update(data.encode())
        return h.hexdigest()

    def create_block(self, block_num):
        block_hash = self.create_hash(data=block_num)
        tx_hash = self.create_hash(data=f'{block_num}{block_hash}')

        return {
            'number': block_num,
            'hash': block_hash,
            'processed': {
                'hash': tx_hash
            }
        }

    def create_block_files(self, num_files):
        for i in range(num_files):
            rand_int = random.randint(int(time.time()) - 2 * 365 * 24 * 60 * 60, int(time.time())) * 1000000000

            block_num = str(rand_int).zfill(64)
            block_hash = self.create_hash(data=block_num)
            tx_hash = self.create_hash(data=f'{block_num}{block_hash}')

            block_path = os.path.join(self.blocks_path, block_num)
            tx_path = os.path.join(self.txs_path, tx_hash)
            alias_path = os.path.join(self.alias_path, block_hash)

            block_data = self.create_block(block_num=block_num)

            tx_data = block_data.get('processed')
            block_data['processed'] = tx_hash

            # create block file
            with open(block_path, 'w') as f:
                json.dump(block_data, f)

            # create tx file
            with open(tx_path, 'w') as f:
                json.dump(tx_data, f)

            # create tx_hash link to block file
            os.symlink(block_path, alias_path)



    def test_migrate_blocks_dir_works(self):
        self.create_block_files(10)

        block_migration = MigrateFiles(
            src_path=self.blocks_path,
            dest_path=self.blocks_dest_path
        )

        block_migration.start()

        for filename in block_migration.migrated_files:
            migrated_file = self.block_driver.find_block(
                block_num=filename
            )
            block = self.create_block(block_num=filename)
            self.assertDictEqual(block, migrated_file)



