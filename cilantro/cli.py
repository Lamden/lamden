import click
import os
from cilantro.protocol import wallet
import json
from simplecrypt import encrypt, decrypt
import getpass
import hashlib
import requests

configuration_path = '/usr/local/share/lamden/cilantro'
directory_file = 'dir.conf'
network_file = 'net.conf'

default_directory = '~/cilantro'
default_crawl = '127.0.0.1'


def get_password():
    confirm = None
    password = None
    while password != confirm or password is None:
        password = getpass.getpass('Password:')
        confirm = getpass.getpass('Confirm:')
        if password != confirm:
            print('Passwords do not match.')
    return password


def signing_key_for_keyfile(filename):
    assert os.path.isfile(filename)

    _key = json.load(open(filename))
    if len(_key['s']) > 64:
        password = get_password()
        s = bytes.fromhex(_key['s'])
        print('Decrypting from 100,000 iterations...')

        decoded_s = decrypt(password, s)
        _key['s'] = decoded_s.decode()
    return _key['s']



@click.group()
def main():
    pass


@main.command('key', short_help='Generate a new key.')
@click.option('-o', '--output', 'output', help='Filename where the key will be saved.')
@click.option('-r', '--raw', is_flag=True, help='Flag to bypass encryption and produce a raw key.')
@click.option('-s', '--seed', 'seed', help='Passes a deterministic payload to the key generator.')
def key(output, raw, seed):

    output = os.path.realpath(output)

    if seed:
        sha = hashlib.sha3_256()
        sha.update(seed.encode())
        seed = sha.digest()

    s, v = wallet.new() if not seed else wallet.new(seed=seed)
    w = {'s': s, 'v': v}

    if not raw:
        password = get_password()
        if password != '':
            click.echo(click.style('Encrypting to 100,000 iterations...', fg='blue'))
            w['s'] = encrypt(password, w['s']).hex()

    if output:
        if os.path.isfile(output):
            click.echo(click.style('Key at {} already exists.'.format(output), fg='red'))
        else:
            with open(output, 'w') as f:
                json.dump(w, f)
            click.echo(click.style('New key written to {}'.format(output), fg='green'))
    else:
        print(w)

# sign <data> <output> <key>
@main.command('sign', short_help='Sign some data.')
@click.option('-k', '--keyfile', 'keyfile')
@click.option('-d', '--data', 'data')
def sign(keyfile, data):
    if not keyfile:
        print('get default keyfile from conf')
    elif os.path.isfile(keyfile) and data:
        key = json.load(open(keyfile))
        if len(key['s']) > 64:
            password = get_password()
            s = bytes.fromhex(key['s'])
            click.echo(click.style('Decrypting from 100,000 iterations...', fg='blue'))
            try:
                decoded_s = decrypt(password, s)
                key['s'] = decoded_s.decode()
            except Exception as e:
                click.echo(click.style('{}'.format(e), fg='red'))

        print(wallet.sign(key['s'], data.encode()))

    else:
        click.echo(click.style('Keyfile does not exist or data was not provided.', fg='red'))


@main.command('estimate', short_help='Get the Compute Units (CUs) required to publish a smart contract or transaction.')
@click.option('-d', '--data', 'data')
def estimate(data):
    print('will interface with falcons code')

# publish <data> <key> --cleanup
@main.command('publish', short_help='Publishes a signed smart contract or transaction to the network.')
@click.option('-d', '--data', 'data')
def publish(data):
    print('TBD')


############################################################
# GET COMMANDS SUBGROUP
############################################################

@click.group('get')
def get():
    pass


@get.command('block')
@click.argument('num')
@click.option('-i', '--ip', 'ip')
@click.option('-h', '--hash', '_hash', is_flag=True)
def get_block(ip, _hash, num):
    j = {'hash': num} if hash else {'number': num}
    r = requests.get('http://{}:8080/blocks'.format(ip), json=j)
    print(r.text)


@get.command('balance')
@click.argument('address')
def get_balance(address):
    print(address)


@get.command('contract')
@click.argument('address')
@click.option('-m', '--methods', 'methods', is_flag=True, help='Parse and return just the methods this contract offers.')
@click.option('-d', '--datatypes', 'datatypes', is_flag=True, help='Parse and return data types this contract accesses.')
def get_balance(address, methods, datatypes):
    if methods:
        print('methods')
    elif datatypes:
        print('datatypes')
    print(address)


############################################################
# SET COMMANDS SUBGROUP
############################################################

@click.group('set')
def _set():
    pass


@_set.command('key')
@click.argument('keyfile')
def set_key(keyfile):
    try:
        s = signing_key_for_keyfile(os.path.realpath(keyfile))
        os.environ['SESSION_KEY'] = s
        click.echo(click.style('Session key successfully set! Ending this session will remove your key from memory '
                               'for security. You can now sign and publish transactions without specifying a key.',
                               fg='green'))
    except Exception as e:
        click.echo(click.style('{}'.format(e), fg='red'))


@_set.command('directory')
@click.argument('directory')
def set_directory(directory):
    directory = os.path.realpath(directory)
    default_path = os.path.join(configuration_path, directory_file)
    with open(default_path, 'w') as f:
        f.write(directory)


@_set.command('network')
@click.argument('network')
def set_network(network):
    default_path = os.path.join(configuration_path, network_file)
    with open(default_path, 'w') as f:
        f.write(network)

main.add_command(get)
main.add_command(_set)

if __name__ == '__main__':
    print('yo2')