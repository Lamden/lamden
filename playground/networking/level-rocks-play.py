from cilantro.utils.constants import BALANCE_KEY
import plyvel

# print('quack')
# db.close()


class LevelsDriver:
    def __init__(self, path):
        self.db = plyvel.DB(path, create_if_missing=True)

    def get_balance(self, wallet):
        return self.db.get(BALANCE_KEY + wallet)

    def set_balance(self, wallet, amount):
        return self.db.put(BALANCE_KEY + wallet, amount)

    def seed_state(self, balances: dict):
        for wallet_key, balance in balances.items():
            self.set_balance(wallet_key, balance)

    def flush(self):
        """
        Flushes all balances
        """
        for k, v in self.db.iterator(start=BALANCE_KEY):
            self.db.delete(k)

l = LevelsDriver(path='/tmp/testdb/')
l.set_balance(wallet=b'stu', amount=b'100')
print(l.get_balance(wallet=b'stu'))