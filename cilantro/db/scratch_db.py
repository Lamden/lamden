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
        # TODO -- implement
        return False

    def get_balance(self, wallet_key: str, wallet: Wallet=BasicWallet) -> float:
        """
        Retrieves the current scratch balance for the wallet
        :param wallet_key: The verifying address for the wallet
        :param wallet: a Wallet object whose balance will be checked
        :return: A float representing the current balance of the wallet
        """
        # TODO -- implement
        val = 50
        print('getting scratch balance for wallet: {}...value: {}'.format(str(wallet_key), val))
        return val

    def set_balance(self, wallet_key: str, balance: float, wallet: Wallet=BasicWallet, ):
        """
        Sets the current scratch balance of the wallet
        :param wallet_key: The verifying address for the wallet
        :param wallet: a Wallet object whose balance will be checked
        :param balance: A float representing the balance to set the wallet to
        :return:
        """
        # TODO -- implement
        print('setting scratch balance for wallet: {} to value: {}'.format(wallet_key, balance))

    def flush(self):
        """
        Flushes all balances in the scratch
        :return:
        """
        # TODO -- implement
        print('flushing scratch')
        pass
