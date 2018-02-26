from cilantro.nodes.delegate.db.driver_base import DriverBase
from cilantro.utils.constants import SCRATCH_KEY
from cilantro.utils.utils import RedisSerializer as RS


class ScratchDriver(DriverBase):

    def wallet_exists(self, wallet_key: str) -> bool:
        """
        Checks if the wallet exists in the scratch
        :param wallet_key: The verifying address for the wallet
        :return: True if the wallet exists in the scratch, or false otherwise
        """
        return self.r.hexists(SCRATCH_KEY, wallet_key)

    def get_balance(self, wallet_key: str) -> float:
        """
        Retrieves the current scratch balance for the wallet
        :param wallet_key: The verifying address for the wallet
        :return: A float representing the current balance of the wallet
        """
        return RS.float(self.r.hget(SCRATCH_KEY, wallet_key))

    def set_balance(self, wallet_key: str, balance: float):
        """
        Sets the current scratch balance of the wallet
        :param wallet_key: The verifying address for the wallet
        :param balance: A float representing the balance to set the wallet to
        :return:
        """
        self.r.hset(SCRATCH_KEY, wallet_key, balance)

    def flush(self):
        """
        Flushes all balances in the scratch
        :return:
        """
        for item in self.r.hscan_iter(SCRATCH_KEY):
            self.r.hdel(SCRATCH_KEY, item[0])
