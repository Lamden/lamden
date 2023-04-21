import os
import sys
import json
from lamden.storage import FSBlockDriver, FSHashStorageDriver
import shutil


class MigrateFiles:
    def __init__(self, src_path, dest_path, testing=False):
        self.testing = testing

        self.blocks_path_src = src_path
        self.block_alias_path_src = os.path.join(self.blocks_path_src, 'alias')
        self.txs_path_src = os.path.join(self.blocks_path_src, 'txs')

        self.blocks_path_dest = os.path.abspath(dest_path)
        self.block_alias_path_dest = os.path.abspath(os.path.join(os.path.dirname(self.blocks_path_dest), 'block_alias'))
        self.txs_path_dest = os.path.abspath(os.path.join(os.path.dirname(self.blocks_path_dest), 'txs'))

        self.migrated_files: list = []

    def _create_directories(self):
        if os.path.exists(self.blocks_path_dest):
            shutil.rmtree(self.blocks_path_dest)

        os.makedirs(self.blocks_path_dest)

    def start(self):
        self._create_directories()

        block_driver = FSBlockDriver(root=self.blocks_path_dest)
        block_alias_driver = FSHashStorageDriver(root=self.block_alias_path_dest)
        tx_driver = FSHashStorageDriver(root=self.txs_path_dest)

        for root, _, files in os.walk(self.blocks_path_src):
            for filename in files:
                if filename.isdigit():
                    src_file = os.path.join(root, filename)

                    moved_to = block_driver.move_block(src_file, filename)

                    block = block_driver.find_block(block_num=filename)

                    # if isinstance(block, str):
                    #    block = json.loads(block)

                    block_hash = block.get('hash')
                    block_alias_driver.write_symlink(
                        hash_str=block_hash,
                        link_to=moved_to
                    )

                    if int(filename) != 0:
                        tx_hash = block['processed']
                        with open(os.path.join(self.txs_path_src, tx_hash)) as file:
                            data = json.loads(file.read())
                            tx_driver.write_file(
                                hash_str=tx_hash,
                                data=data
                            )

                    if self.testing:
                        self.migrated_files.append(filename)

        shutil.rmtree(self.blocks_path_src)
        os.rename(self.blocks_path_dest, self.blocks_path_src)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python migrate_blocks_dir.py <source_directory> <destination_directory>")
        sys.exit(1)

    source_directory = sys.argv[1]
    destination_directory = sys.argv[2]

    block_file_migrator = MigrateFiles(source_directory, destination_directory)
    block_file_migrator.start()
    print("Migration completed.")
