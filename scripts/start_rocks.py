import os, sys
from cilantro_ee.constants.db_config import DATA_DIR

ROCKS_DIR = DATA_DIR + '/rocks'

def start_rocks():
    print("Starting Rocks server...")
    if not os.path.exists(ROCKS_DIR):
        print("Creating Rocks directory at {}".format(ROCKS_DIR))
        os.makedirs(ROCKS_DIR, exist_ok=True)

    print("Rocks using data directory: {}".format(ROCKS_DIR))

    # cmd = f"export LC_ALL=en_US.UTF-8; export LANG=C.UTF-8; rocks serve -d {ROCKS_DIR}"
    cmd = f"export LC_ALL=C.UTF-8; export LANG=C.UTF-8; rocks serve -d {ROCKS_DIR} &"
    # os.system('export LC_ALL=C.UTF-8; export LANG=C.UTF-8; rocks serve -d /Users/lamden/lamden/rocks')
    # os.system('export LC_ALL=en_US.UTF-8; export LANG=C.UTF-8; rocks serve -d ROCKS_DIR')
    os.system(cmd)

if __name__ == '__main__':
    start_rocks()

