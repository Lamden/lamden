from pathlib import Path
import uuid
import shutil
import os
from contracting.db.encoder import decode

from lamden.config import STORAGE_HOME
from lamden.logger.base import get_logger


class FileQueue:
    EXTENSION = '.tx'

    def __init__(self, root=STORAGE_HOME.joinpath('txq'), sort_key=os.path.getmtime, write_bytes=True, reverse=False):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.log = get_logger("FILE QUEUE")
        self.file_mode = 'wb' if write_bytes else 'w'
        self.sort_key = sort_key
        self.reverse = reverse

    def append(self, tx, name=None):
        if name is None:
            name = str(uuid.uuid4()) + self.EXTENSION
        with open(self.root.joinpath(name), self.file_mode) as f:
            f.write(tx)

    def pop(self, idx, return_time=False):
        items = sorted(self.root.iterdir(), key=self.sort_key)

        if self.reverse:
            items = items[::-1]

        item = items.pop(idx)

        with open(item) as f:
            i = decode(f.read())

        if return_time:
            time = os.path.getmtime(item)
            os.remove(item)
            return i, time

        os.remove(item)
        return i

    def flush(self):
        try:
            shutil.rmtree(self.root)
        except FileNotFoundError:
            pass

    def refresh(self):
        self.flush()
        os.makedirs(self.root)

    def __len__(self):
        try:
            length = len(list(self.root.iterdir()))
            return length
        except FileNotFoundError:
            return 0

    def __getitem__(self, key):
        items = sorted(self.root.iterdir(), key=self.sort_key)
        item = items[key]

        with open(item) as f:
            i = decode(f.read())

        return i
