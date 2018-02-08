import redis
from cilantro.db.base_db import BaseDB

from cilantro.wallets.core import Wallet
from cilantro.wallets.basic import BasicWallet

class BalanceDB(BaseDB):

    def get_balance(self, wallet_key: str, wallet: Wallet=BasicWallet) -> float:
        """
        Retrieves the current balance for the wallet
        :param wallet: a Wallet object whose balance will be checked
        :param wallet_key: The verifying address for the wallet
        :return: A float representing the current balance of the wallet
        """
        pass

    def set_balance(self, wallet_key: str, balance: float, wallet: Wallet=BasicWallet):
        """
        Sets the balance of the wallet
        :param wallet: a Wallet object whose balance will be checked
        :param wallet_key: The verifying address for the wallet
        :param balance: A float representing the balance to set the wallet to
        :return: void
        """
        pass