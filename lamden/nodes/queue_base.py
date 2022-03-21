import asyncio
from lamden.nodes.filequeue import FileQueue
import os
class ProcessingQueue:
    def __init__(self):
        self.running = False
        self.paused = False
        self.currently_processing = False

        self.queue = []

    def __len__(self):
        return len(self.queue)

    def __getitem__(self, index):
        try:
            return self.queue[index]
        except IndexError:
            return None

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def pause(self):
        self.paused = True

    def unpause(self):
        self.paused = False

    def start_processing(self):
        self.currently_processing = True

    def stop_processing(self):
        self.currently_processing = False

    @property
    def active(self):
        return self.running and not self.paused

    async def stopping(self):
        while self.currently_processing:
            await asyncio.sleep(0)

    async def pausing(self):
        while self.currently_processing:
            await asyncio.sleep(0)

    def flush(self):
        self.queue = []

    def append(self, item):
        self.queue.append(item)

    async def process_next(self):
        raise NotImplementedError


class ProcessingFileQueue:
    def __init__(self, root, sort_key, write_bytes=True):
        self.running = False
        self.paused = False
        self.currently_processing = False

        self.q = []

        self.queue = FileQueue(root=root, sort_key=sort_key, write_bytes=write_bytes)

    def __len__(self):
        return len(self.queue)

    def __getitem__(self, index):
        try:
            return self.queue[index]
        except IndexError:
            return None

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def pause(self):
        self.paused = True

    def unpause(self):
        self.paused = False

    def start_processing(self):
        self.currently_processing = True

    def stop_processing(self):
        self.currently_processing = False

    @property
    def active(self):
        return self.running and not self.paused

    async def stopping(self):
        while self.currently_processing:
            await asyncio.sleep(0)

    async def pausing(self):
        while self.currently_processing:
            await asyncio.sleep(0)

    def flush(self):
        self.queue.flush()

    def append(self, item, name=None):
        self.queue.append(item, name=name)

    async def process_next(self):
        raise NotImplementedError