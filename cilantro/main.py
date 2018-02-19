import click
import os
from getpass import getpass
from cilantro.wallets import ED25519Wallet
from datetime import datetime

UNLOCKED_WALLET = None

import nacl.secret
import nacl.utils

async def cli_loading_animation():
    pass

def pad_bytes(b):
    while len(b) < 32:
        b += b'0'
    return b

@click.command()
@click.option('--file_dir', default=None)
def new_wallet(file_dir):
    if file_dir is None:
        file_dir = os.getcwd()

    # securely get the password to salt the wallet signing key
    password = getpass('Enter a password to secure the wallet: ')

    # size password to 32 bytes for ed25519 encryption
    password = password.encode()[:32]
    password = pad_bytes(password)
    print(password)

    box = nacl.secret.SecretBox(password)

    wallet = ED25519Wallet.new()
    signing_key = bytes.fromhex(wallet[0])

    encrypted_wallet = box.encrypt(signing_key)

    print(encrypted_wallet)

    # output wallet as a UTC timestamp for simplicity
    now = datetime.utcnow()
    file_name = 'UTC-' + str(now).replace(' ', '-') + '.tau'

    print('Generated new wallet in {}'.format(os.path.join(file_dir, file_name)))

    with open(os.path.join(file_dir, file_name), 'wb') as f:
        f.write(encrypted_wallet)

@click.command()
@click.argument('address')
@click.argument('amount')
def send():
    print('hello')


if __name__ == '__main__':
    new_wallet()
