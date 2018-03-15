from cilantro.nodes.delegate.db.driver_base import DriverBase
from cilantro.utils.constants import BALANCE_KEY
from cilantro.utils.utils import Encoder as E


class BalanceDriver(DriverBase):

    def get_balance(self, wallet_key: str) -> float:
        """
        Retrieves the current balance for the wallet
        :param wallet_key: The verifying address for the wallet
        :return: A float representing the current balance of the wallet
        """
        if self.r.hexists(BALANCE_KEY, wallet_key):
            return E.float(self.r.hget(BALANCE_KEY, wallet_key))
        else:
            # raise Exception('(get_balance) Balance could not be found for key: {}'.format(wallet_key))
            print('(get_balance) Balance could not be found for key: {} ... returning 0'.format(wallet_key))
            return 0

    def set_balance(self, wallet_key: str, balance: float):
        """
        Sets the balance of the wallet
        :param wallet_key: The verifying address for the wallet
        :param balance: A float representing the balance to set the wallet to
        :return: void
        """
        self.r.hset(BALANCE_KEY, wallet_key, balance)

    def seed_state(self, balances: dict):
        for wallet_key, balance in balances.items():
            self.set_balance(wallet_key, balance)

    def flush(self):
        """
        Flushes all balances
        """
        for item in self.r.hscan_iter(BALANCE_KEY):
            self.r.hdel(BALANCE_KEY, item[0])

