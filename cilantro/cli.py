import click
import os
from cilantro.protocol import wallet
import json
from simplecrypt import encrypt, decrypt
import getpass

configuration_path = '/usr/local/share/lamden'
configuration_filename = 'cilantro.conf'

default_directory = '~/cilantro'
default_crawl = '127.0.0.1'


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
@click.option('-i', '--info', is_flag=True)
@click.option('-d', '--directory', 'directory')
@click.option('-n', '--network', 'network')
def config(info, directory, network):
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


@main.command('key', short_help='Generate a new key.')
@click.option('-o', '--output', 'output')
@click.option('-r', '--raw', is_flag=True)
@click.option('-s', '--seed', 'seed')
def key(output, raw, seed):

    s, v = wallet.new() if not seed else wallet.new(seed=seed)
    w = {'s': s, 'v': v}

    if not raw:
        confirm = None
        password = None
        while password != confirm or password is None:
            password = getpass.getpass('Password:')
            confirm = getpass.getpass('Confirm:')
            if password != confirm:
                print('Passwords do not match.')
        if password != '':
            click.echo(click.style('Encrypting...', fg='blue'))
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

if __name__ == '__main__':
    print('yo2')