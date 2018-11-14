import click
import os
from cilantro.protocol import wallet
import json
from simplecrypt import encrypt, decrypt
import getpass
import hashlib
import requests

configuration_path = '/usr/local/share/lamden'
configuration_filename = 'cilantro.conf'

default_directory = '~/cilantro'
default_crawl = '127.0.0.1'
default_keyfile = 'NULL'

defaults = {
    'directory': default_directory,
    'crawl': default_crawl,
    'keyfile': default_keyfile
}

def create_default_configuration_file(d=default_directory, n=default_crawl):

    # rewrite the configuration file for reading later
    with open(configuration_path + '/' + configuration_filename, 'w') as f:
        f.write('{}\n'.format(d))
        f.write('{}'.format(n))


def get_configuration(filename):
    with open(filename) as f:
        directory = f.readline().rstrip('\n')
        network = f.readline()
    return directory, network


@click.group()
def main():
    if not os.path.exists(configuration_path):
        os.makedirs(configuration_path)

    if not os.path.isfile(configuration_path + '/' + configuration_filename):
        create_default_configuration_file()

    d, _ = get_configuration(configuration_path + '/' + configuration_filename)
    if not os.path.exists(os.path.expanduser(d)):
        os.makedirs(os.path.expanduser(d))


# make a directory in.. /usr/local/share/lamden
# cilantro.conf

@main.command('config', short_help='Adjust the default directory and network configuration.')
@click.option('-i', '--info', is_flag=True, help='Outputs the current values of the defaults.')
@click.option('-d', '--directory', 'directory', help='Sets a new directory as the default.')
@click.option('-n', '--network', 'network', help='Sets a new network as the default.')
@click.option('-k', '--keyfile', 'keyfile', help='Sets a new keyfile as the default.')
def config(info, directory, network, keyfile):
    # make sure that the configuration_path path is available
    if info:
        d, n = get_configuration(configuration_path + '/' + configuration_filename)
        print('Directory: {}'.format(d))
        print('Network Crawl: {}'.format(n))
    elif directory:
        create_default_configuration_file(d=directory)
        print('Directory changed to: {}'.format(directory))
    elif network:
        create_default_configuration_file(n=network)
        print('Network Crawl changed to: {}'.format(network))
    elif keyfile:
        print('TBD')


def get_password():
    confirm = None
    password = None
    while password != confirm or password is None:
        password = getpass.getpass('Password:')
        confirm = getpass.getpass('Confirm:')
        if password != confirm:
            print('Passwords do not match.')
    return password


@main.command('key', short_help='Generate a new key.')
@click.option('-o', '--output', 'output', help='Filename where the key will be saved.')
@click.option('-r', '--raw', is_flag=True, help='Flag to bypass encryption and produce a raw key.')
@click.option('-s', '--seed', 'seed', help='Passes a deterministic payload to the key generator.')
def key(output, raw, seed):

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


@main.command('publish', short_help='Publishes a signed smart contract or transaction to the network.')
@click.option('-d', '--data', 'data')
def publish(data):
    print('TBD')


@main.command('latest_block', short_help='Pings mock Masternode.')
@click.option('-i', '--ip', 'ip')
def ping(ip):
    if not ip:
        print('Provide an IP with -i / --ip')
    else:
        r = requests.get('http://{}:8080/latest_block'.format(ip))
        print(r.text)


############################################################
# GET COMMANDS SUBGROUP
############################################################

@click.group('get')
def get():
    print('testing nesting')


@get.command('block')
@click.argument('num')
@click.option('-i', '--ip', 'ip')
def get_block(ip, num):
    print(num)


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


main.add_command(get)

if __name__ == '__main__':
    print('yo2')