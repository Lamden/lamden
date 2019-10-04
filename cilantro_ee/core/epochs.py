from contracting.db.driver import ContractDriver

EPOCH_INTERVAL = 100
EPOCH_HASH_KEY = '__epoch_hash'
EPOCH_NUMBER_KEY = '__epoch_number'


class EpochManager:
    def __init__(self, driver=ContractDriver()):
        self.driver = driver

    def update_epoch_if_needed(self, block):
        if block.blockNum % EPOCH_INTERVAL == 0:
            self.set_epoch_hash(block.blockHash)
            self.set_epoch_number(block.blockNum // EPOCH_INTERVAL)

    def get_epoch_hash(self):
        return self.driver.get(EPOCH_HASH_KEY) or b'x/00' * 32

    def set_epoch_hash(self, value):
        self.driver.set(EPOCH_HASH_KEY, value)

    def get_epoch_number(self):
        return self.driver.get(EPOCH_NUMBER_KEY) or 0

    def set_epoch_number(self, value):
        self.driver.set(EPOCH_NUMBER_KEY, value)
