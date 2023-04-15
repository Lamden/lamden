import os
import sys
from lamden.storage import LayeredDirectoryDriver


class MigrateFiles:
    def __init__(self, src_path, dest_path):
        self.src_path = src_path
        self.dest_path = dest_path

        self.migrated_files: list = []

    def start(self):
        block_driver = LayeredDirectoryDriver(root=self.dest_path)

        for root, _, files in os.walk(self.src_path):
            for file in files:
                if file.isdigit():
                    src_file = os.path.join(root, file)
                    block_driver.move_block(src_file, file)
                    self.migrated_files.append(file)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python migrate_blocks_dir.py <source_directory> <destination_directory>")
        sys.exit(1)

    source_directory = sys.argv[1]
    destination_directory = sys.argv[2]

    block_file_migrator = MigrateFiles(source_directory, destination_directory)
    block_file_migrator.start()
    print("Migration completed.")
