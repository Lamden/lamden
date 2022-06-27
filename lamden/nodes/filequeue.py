from pathlib import Path
import uuid
import shutil
import os
from contracting.db.encoder import decode
import pathlib
from lamden.logger.base import get_logger

STORAGE_HOME = pathlib.Path().home().joinpath('.lamden')

class FileQueue:
    EXTENSION = '.tx'

    def __init__(self, root=STORAGE_HOME.joinpath('txq'), write_bytes=True):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

        self.temp = self.root.parent.joinpath('temp_txq')
        self.temp.mkdir(parents=True, exist_ok=True)

        self.log = get_logger("FILE QUEUE")
        self.file_mode = 'wb' if write_bytes else 'w'

    def append(self, tx):
        name = str(uuid.uuid4()) + self.EXTENSION
        temp_filepath = self.temp.joinpath(name)
        final_filepath = self.root.joinpath(name)

        with open(temp_filepath, self.file_mode) as f:
            f.write(tx)
        os.rename(temp_filepath, final_filepath)

    def pop(self, idx):
        items = sorted(self.root.iterdir(), key=os.path.getmtime)
        item = items.pop(idx)
        with open(item) as f:
            i = decode(f.read())
        os.remove(item)

        return i

    def flush(self):
        try:
            shutil.rmtree(self.root)
        except FileNotFoundError:
            pass
        try:
            shutil.rmtree(self.temp)
        except FileNotFoundError:
            pass

    def refresh(self):
        self.flush()
        self.root.mkdir(exist_ok=True, parents=True)
        self.temp.mkdir(exist_ok=True, parents=True)

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
