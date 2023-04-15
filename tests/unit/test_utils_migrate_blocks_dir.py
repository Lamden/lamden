from lamden.utils.migrate_blocks_dir import MigrateFiles
from lamden.storage import LayeredDirectoryDriver

import os
import shutil
from pathlib import Path
from unittest import TestCase
import random
import time


class TestMigrateBlocksDir(TestCase):
    def setUp(self):
        self.test_dir = './.lamden'
        self.src_dir = 'blocks'
        self.src_path = os.path.join(self.test_dir, self.src_dir)
        self.dest_dir = 'migrated'
        self.dest_path = os.path.join(self.test_dir, self.dest_dir)

        self.block_driver = LayeredDirectoryDriver(root=self.dest_path)

        self.create_directories()

    def tearDown(self):
        pass

    def create_directories(self):
        if os.path.exists(Path(self.test_dir)):
            shutil.rmtree(Path(self.test_dir))

        os.makedirs(Path(self.test_dir))
        os.makedirs(self.src_path)

    def create_block_files(self, num_files):
        zeros_pad_pre = '0' * 36
        zeros_pad_post = '0' * 9
        for i in range(num_files):
            rand_int = random.randint(int(time.time()) - 2 * 365 * 24 * 60 * 60, int(time.time()))
            timestamp = f'{zeros_pad_pre}{rand_int}{zeros_pad_post}'
            file_path = os.path.join(self.test_dir, 'blocks', f"{timestamp}")
            open(file_path, 'w').close()

    def test_migrate_blocks_dir_works(self):
        self.create_block_files(10)

        block_migration = MigrateFiles(
            src_path=self.src_path,
            dest_path=self.dest_path
        )

        block_migration.start()

        for file in block_migration.migrated_files:
            migrated_file = self.block_driver.find_block(
                block_num=file
            )
            self.assertEqual(int(file), int(migrated_file))



