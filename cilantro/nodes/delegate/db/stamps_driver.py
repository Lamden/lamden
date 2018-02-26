from cilantro.nodes.delegate.db.driver_base import DriverBase
from cilantro.utils.constants import STAMP_KEY
from cilantro.utils.utils import RedisSerializer as RS


class StampsDriver(DriverBase):

    def get_balance(self, wallet_key: str) -> float:
        """
        Retrieves the current stamp balance for the wallet
        :param wallet_key: The verifying address for the wallet
        :return: A float representing the current balance of the wallet
        """
        if self.r.hexists(STAMP_KEY, wallet_key):
            return RS.float(self.r.hget(STAMP_KEY, wallet_key))
        else:
            # raise Exception('(get_balance) Balance could not be found for key: {}'.format(wallet_key))
            print('(get_balance) Stamp balance could not be found for key: {} ... returning 0'.format(wallet_key))
            return 0

    def set_balance(self, wallet_key: str, balance: float):
        """
        Sets the stamp balance of the wallet
        :param wallet_key: The verifying address for the wallet
        :param balance: A float representing the balance to set the wallet to
        :return: void
        """
        self.r.hset(STAMP_KEY, wallet_key, balance)
