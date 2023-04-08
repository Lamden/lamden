import os
import sys
from lamden.storage import LayeredDirectoryDriver
def migrate_files(src_dir, dst_dir):
    block_driver = LayeredDirectoryDriver(root=dst_dir)

    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.isdigit():
                src_file = os.path.join(root, file)
                block_driver.move_block(src_file, file)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python migrate.py <source_directory> <destination_directory>")
        sys.exit(1)

    source_directory = sys.argv[1]
    destination_directory = sys.argv[2]

    migrate_files(source_directory, destination_directory)
    print("Migration completed.")
