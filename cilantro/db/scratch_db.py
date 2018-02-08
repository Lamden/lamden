import redis
from cilantro.db.base_db import BaseDB

from cilantro.wallets.core import Wallet
from cilantro.wallets.basic import BasicWallet


class ScratchDB(BaseDB):

    def wallet_exists(self, wallet_key: str, wallet: Wallet=BasicWallet) -> bool:
        """
        Checks if the wallet exists in the scratch
        :param wallet_key: The verifying address for the wallet
        :param wallet: a Wallet object
        :return: True if the wallet exists in the scratch, or false otherwise
        """
        pass

    def get_balance(self, wallet_key: str, wallet: Wallet=BasicWallet) -> float:
        """
        Retrieves the current scratch balance for the wallet
        :param wallet_key: The verifying address for the wallet
        :param wallet: a Wallet object whose balance will be checked
        :return: A float representing the current balance of the wallet
        """
        pass

    def set_balance(self, wallet_key: str, balance: float, wallet: Wallet=BasicWallet, ):
        """
        Sets the current scratch balance of the wallet
        :param wallet_key: The verifying address for the wallet
        :param wallet: a Wallet object whose balance will be checked
        :param balance: A float representing the balance to set the wallet to
        :return:
        """
        pass

    def flush(self):
        """
        Flushes all balances in the scratch
        :return:
        """
        pass
