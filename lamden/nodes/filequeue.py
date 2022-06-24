from pathlib import Path
import uuid
import shutil
import os
from contracting.db.encoder import decode
import pathlib
from lamden.logger.base import get_logger
from threading import Lock

STORAGE_HOME = pathlib.Path().home().joinpath('.lamden')

class FileQueue:
    EXTENSION = '.tx'

    def __init__(self, root=STORAGE_HOME.joinpath('txq'), write_bytes=True):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.log = get_logger("FILE QUEUE")
        self.file_mode = 'wb' if write_bytes else 'w'

        # NOTE: temporary fix to make test_base_node_throughput work
        self.lock = Lock()

    def append(self, tx):
        name = str(uuid.uuid4()) + self.EXTENSION
        # NOTE: temporary fix to make test_base_node_throughput work
        self.lock.acquire()
        with open(self.root.joinpath(name), self.file_mode) as f:
            f.write(tx)
        self.lock.release()

    def pop(self, idx):
        items = sorted(self.root.iterdir(), key=os.path.getmtime)
        item = items.pop(idx)
        # NOTE: temporary fix to make test_base_node_throughput work
        self.lock.acquire()
        with open(item) as f:
            i = decode(f.read())
        self.lock.release()
        os.remove(item)

        return i

    def flush(self):
        try:
            shutil.rmtree(self.root)
        except FileNotFoundError:
            pass

    def refresh(self):
        self.flush()
        self.root.mkdir(exist_ok=True, parents=True)

    def __len__(self):
        try:
            length = len(list(self.root.iterdir()))
            return length
        except FileNotFoundError:
            return 0

    def __getitem__(self, key):
        items = sorted(self.root.iterdir(), key=os.path.getmtime)
        item = items[key]

        with open(item) as f:
            i = decode(f.read())

        return i
