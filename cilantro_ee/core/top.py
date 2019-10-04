from contracting.db.driver import ContractDriver

BLOCK_HASH_KEY = '__last_block_hash'
BLOCK_NUMBER_KEY = '__last_block_number'


class TopBlockManager:
    def __init__(self, driver=ContractDriver()):
        self.driver = driver

    def get_latest_block_hash(self):
        return self.driver.get(BLOCK_HASH_KEY) or b'\x00' * 32

    def set_latest_block_hash(self, value):
        self.driver.set(BLOCK_HASH_KEY, value)

    def get_latest_block_number(self):
        return self.driver.get(BLOCK_NUMBER_KEY) or 0

    def set_latest_block_number(self, value):
        self.driver.set(BLOCK_NUMBER_KEY, value)
