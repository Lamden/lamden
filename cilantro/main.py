import click
import os
from getpass import getpass
from cilantro.wallets import ED25519Wallet
from datetime import datetime
import xxtea

UNLOCKED_WALLET = None

@click.command()
@click.option('--file_dir', default=None)
def new_wallet(file_dir):
    if file_dir is None:
        file_dir = os.getcwd()

    # securely get the password to salt the wallet signing key
    password = getpass('Enter a password to secure the wallet: ')

    wallet = ED25519Wallet.new()
    signing_key = bytes.fromhex(wallet[0])

    encrypted_wallet = xxtea.encrypt(signing_key, password)

    print(encrypted_wallet)

    # output wallet as a UTC timestamp for simplicity
    now = datetime.utcnow()
    file_name = 'UTC-' + str(now).replace(' ', '-') + '.tau'

    print('Generated new wallet in {}'.format(os.path.join(file_dir, file_name)))

    with open(os.path.join(file_dir, file_name), 'wb') as f:
        f.write(encrypted_wallet)


def unlock_wallet():

    with open(os.path.join(os.path.join(os.getcwd(), 'test.tau')), 'rb') as f:
        encrypted_wallet = f.read()
    password = getpass('Enter the password to unlock the wallet: ')
    signing_key = xxtea.decrypt(encrypted_wallet, password)
    UNLOCKED_WALLET = signing_key

    print(UNLOCKED_WALLET)


@click.command()
@click.argument('address')
@click.argument('amount')
def send():
    print('hello')


if __name__ == '__main__':
    #new_wallet(None)
    unlock_wallet()
