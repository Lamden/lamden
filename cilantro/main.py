import click
import os
from getpass import getpass
from simplecrypt import encrypt, decrypt
from cilantro.wallets import ED25519Wallet
from datetime import datetime

UNLOCKED_WALLET = None


async def cli_loading_animation():
    pass


@click.command()
@click.option('--file_dir', default=None)
def new_wallet(file_dir):
    if file_dir is None:
        file_dir = os.getcwd()

    # securely get the password to salt the wallet signing key
    password = getpass('Enter a password to secure the wallet: ')
    print('Generating wallet...')

    # generate a new wallet
    wallet = ED25519Wallet.new()
    signing_key = bytes.fromhex(wallet[0])

    # encrypt with the password
    print('Encrypting wallet...')
    encrypted_wallet = encrypt(password, signing_key)

    print(encrypted_wallet)

    # output wallet as a UTC timestamp for simplicity
    now = datetime.utcnow()
    file_name = 'UTC-' + str(now).replace(' ', '-') + '.tau'

    print('creating new wallet in {}'.format(os.path.join(file_dir, file_name)))

    with open(os.path.join(file_dir, file_name), 'wb') as f:
        f.write(encrypted_wallet)

    print('done')


@click.command()
@click.argument('address')
@click.argument('amount')
def send():
    print('hello')


if __name__ == '__main__':
    new_wallet()
