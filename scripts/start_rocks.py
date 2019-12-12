import os, sys
from cilantro_ee.constants.db_config import DATA_DIR
from rocks.server import RocksDBServer
import asyncio

ROCKS_DIR = DATA_DIR + '/rocks'


def start_rocks(reset=False):
    print("Starting Rocks server...")
    if not os.path.exists(ROCKS_DIR):
        print("Creating Rocks directory at {}".format(ROCKS_DIR))
        os.makedirs(ROCKS_DIR, exist_ok=True)

    print("Rocks using data directory: {}".format(ROCKS_DIR))

    s = RocksDBServer(filename=ROCKS_DIR)

    if reset:
        try:
            s.flush()
        except:
            pass

    loop = asyncio.get_event_loop()
    loop.run_until_complete(s.serve())


if __name__ == '__main__':
    if len(sys.argv) > 1:
        start_rocks(reset=bool(sys.argv[1]))
    else:
        start_rocks()

