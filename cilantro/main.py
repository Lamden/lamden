import click
import os
from getpass import getpass
from cilantro.wallets import ED25519Wallet
from datetime import datetime
import xxtea

UNLOCKED_WALLET = None


async def cli_loading_animation():
    pass


def pad_bytes(b):
    while len(b) < 32:
        b += b'0'
    return b


def format_password(p):
    password = p.encode()[:32]
    password = pad_bytes(password)
    return password


def password_as_nonce(p):
    assert len(p) >= 24, 'Provided password is not long enough. Must be at least 24 bytes.'
    return p[:24]

@click.command()
@click.option('--file_dir', default=None)
def new_wallet(file_dir):
    if file_dir is None:
        file_dir = os.getcwd()

    # securely get the password to salt the wallet signing key
    password = getpass('Enter a password to secure the wallet: ')

    # size password to 32 bytes for ed25519 encryption


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

    print(signing_key)

@click.command()
@click.argument('address')
@click.argument('amount')
def send():
    print('hello')


if __name__ == '__main__':
    #new_wallet(None)
    unlock_wallet()
