from lamden.utils.migrate_blocks_dir import MigrateFiles
from lamden.storage import FSBlockDriver

import os
import shutil
from pathlib import Path
from unittest import TestCase
import random
import time
import json


class TestMigrateBlocksDir(TestCase):
    def setUp(self):
        self.test_dir = './.lamden'
        self.src_dir = 'blocks'
        self.src_path = os.path.join(self.test_dir, self.src_dir)
        self.dest_dir = 'migrated'
        self.dest_path = os.path.join(self.test_dir, self.dest_dir)

        self.create_directories()
        self.block_driver = FSBlockDriver(root=self.dest_path)


    def tearDown(self):
        pass

    def create_directories(self):
        if os.path.exists(Path(self.test_dir)):
            shutil.rmtree(Path(self.test_dir))

        os.makedirs(Path(self.test_dir))
        os.makedirs(self.src_path)
        os.makedirs(self.dest_path)

    def create_block_files(self, num_files):
        for i in range(num_files):
            rand_int = random.randint(int(time.time()) - 2 * 365 * 24 * 60 * 60, int(time.time())) * 1000000000
            timestamp = str(rand_int).zfill(64)
            file_path = os.path.join(self.test_dir, 'blocks', timestamp)

            with open(file_path, 'w') as f:
                json.dump({'number': timestamp}, f)


    def test_migrate_blocks_dir_works(self):
        self.create_block_files(10)

        block_migration = MigrateFiles(
            src_path=self.src_path,
            dest_path=self.dest_path
        )

        block_migration.start()

        for filename in block_migration.migrated_files:
            migrated_file = self.block_driver.find_block(
                block_num=filename
            )
            self.assertDictEqual({'number': filename}, migrated_file)



