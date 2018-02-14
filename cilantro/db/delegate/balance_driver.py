from cilantro.db.delegate.driver_base import DriverBase
from cilantro.db.constants import BALANCE_KEY
from cilantro.db.utils import RedisSerializer as RS


class BalanceDriver(DriverBase):

    def get_balance(self, wallet_key: str) -> float:
        """
        Retrieves the current balance for the wallet
        :param wallet_key: The verifying address for the wallet
        :return: A float representing the current balance of the wallet
        """
        if self.r.hexists(BALANCE_KEY, wallet_key):
            return RS.float(self.r.hget(BALANCE_KEY, wallet_key))
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
