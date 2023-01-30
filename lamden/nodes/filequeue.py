from contracting.db.encoder import decode
from lamden.logger.base import get_logger
from pathlib import Path
import os
import pathlib
import shutil
import uuid

STORAGE_HOME = pathlib.Path().home().joinpath('.lamden')

class FileQueue:
    EXTENSION = '.tx'

    def __init__(self, root=None, write_bytes=True):
        self.log = get_logger("TX QUEUE")
        self.file_mode = 'wb' if write_bytes else 'w'
        self.root = Path(root) if root is not None else STORAGE_HOME
        self.txq = self.root.joinpath('txq')
        self.temp_txq = self.root.joinpath('temp_txq')

        self.__build_directories()
        self.log.debug(f'Created TX queue at \'{self.root}\'')

    def append(self, tx):
        if tx is None:
            return

        filename = str(uuid.uuid4()) + self.EXTENSION
        temp_filepath = self.temp_txq.joinpath(filename)
        final_filepath = self.txq.joinpath(filename)

        with open(temp_filepath, self.file_mode) as f:
            f.write(tx)

        os.rename(temp_filepath, final_filepath)

    def pop(self, idx):
        files = sorted(self.txq.iterdir(), key=os.path.getmtime)
        try:
            file = files.pop(idx)
        except IndexError as err:
            self.log.debug(err)
            return None

        with open(file) as f:
            data = decode(f.read())

        os.remove(file)

        return data

    def flush(self):
        if self.txq.is_dir():
            shutil.rmtree(self.txq)
        if self.temp_txq.is_dir():
            shutil.rmtree(self.temp_txq)

        self.__build_directories()
        self.log.debug(f'Flushed TX queue at \'{self.root}\'')

    def __len__(self):
        try:
            return len(list(self.txq.iterdir()))
        except FileNotFoundError:
            return 0

    def __getitem__(self, key):
        files = sorted(self.txq.iterdir(), key=os.path.getmtime)
        file = files[key]

        with open(file) as f:
            data = decode(f.read())

        return data

    def __build_directories(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.txq.mkdir(parents=True, exist_ok=True)
        self.temp_txq.mkdir(parents=True, exist_ok=True)
