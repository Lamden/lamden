import click
import os
from cilantro_ee.protocol import wallet
import json
from simplecrypt import encrypt, decrypt
import getpass
import hashlib
from seneca.engine.client import SenecaClient
from cilantro_ee.constants.conf import CilantroConf
from cilantro_ee.messages.transaction.contract import ContractTransactionBuilder
from cilantro_ee.constants.vmnet import generate_constitution
from cilantro_ee import tools

configuration_path = '/usr/local/share/lamden/cilantro_ee'
directory_file = 'dir.conf'
network_file = 'net.conf'

default_directory = '~/cilantro_ee'
default_crawl = '127.0.0.1'

_cil_text = \
    r'''
          _ _             _
      ___(_) | __ _ _ __ | |_ _ __ ___
     / __| | |/ _` | '_ \| __| '__/ _ \
    | (__| | | (_| | | | | |_| | | (_) |
     \___|_|_|\__,_|_| |_|\__|_|  \___/

     = = = = A N A R C H Y N E T = = = =

    '''


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


@main.command('hi', short_help='Prints a fun message.')
def hi():
    click.echo(click.style(_cil_text, fg='green'))


############################################################
# GET COMMANDS SUBGROUP
############################################################


@click.group('get', short_help='Subcommand group for getting information from the Cilantro network.')
def get():
    pass


@get.command('block')
@click.argument('block_number')
@click.argument('server_url')
@click.option('-h', '--hash', '_hash', is_flag=True)
def get_block(block_number, server_url, _hash):
    if _hash:
        r = tools.get_block(server_url=server_url, block_hash=block_number)
    else:
        r = tools.get_block(server_url=server_url, block_number=block_number)
    print(r.text)


@get.command('transaction', help='Gets a transaction given a certain hash.')
@click.argument('tx_hash')
@click.argument('server_url')
def get_transaction(tx_hash, server_url):
    r = tools.get_transaction(tx_hash, server_url)
    print(r.text)


@get.command('transactions', help='Gets all transactions given a block hash.')
@click.argument('block_hash')
@click.argument('server_url')
def get_transactions(block_hash, server_url):
    r = tools.get_transactions(block_hash, server_url)
    print(r.text)


@get.command('balance')
@click.argument('address')
def get_balance(address):
    print(address)


@get.command('contract')
@click.argument('contract_address')
def get_contract(contract_address, server_url):
    r = tools.get_contract(contract_address, server_url)
    print(r.text)

@get.command('contract_meta')
@click.argument('contract_address')
def get_contract_meta(contract_address, server_url):
    r = tools.get_contract_meta(contract_address, server_url)
    print(r)

@get.command('state')
@click.argument('contract')
@click.argument('resource_prefix')
@click.argument('key')
def get_state_variable(contract, resource_prefix, key):
    pass


@get.command('estimate', short_help='Get the Compute Units (CUs) required to publish a smart contract or transaction.')
@click.option('-d', '--data', 'data')
def estimate(data):
    print('will interface with falcons code')

############################################################
# SET COMMANDS SUBGROUP
############################################################


@click.group('set', short_help='Subcommand group for setting environment information specific to your computer.')
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
    click.echo(click.style('Default directory set to {}.'.format(directory), fg='green'))


@_set.command('network')
@click.argument('network')
def set_network(network):
    default_path = os.path.join(configuration_path, network_file)
    with open(default_path, 'w') as f:
        f.write(network)
    click.echo(click.style('Network crawl start range set to {}.'.format(network), fg='green'))


############################################################
# NEW COMMANDS SUBGROUP
############################################################


@click.group('new', short_help='Subcommand group for creating new resources such as keys.')
def _new():
    pass


@_new.command('key')
@click.option('-o', '--output', 'output', help='Filename where the key will be saved.')
@click.option('-r', '--raw', is_flag=True, help='Flag to bypass encryption and produce a raw key.')
@click.option('-s', '--seed', 'seed', help='Passes a deterministic payload to the key generator.')
def key(output, raw, seed):

    if output:
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


@_new.command('signature')
@click.option('-k', '--keyfile', 'keyfile')
@click.option('-d', '--data', 'data')
def sign(keyfile, data):
    if not keyfile:
        print('get default keyfile from conf')
    elif os.path.isfile(keyfile) and data:
        _key = json.load(open(keyfile))
        if len(key['s']) > 64:
            password = get_password()
            s = bytes.fromhex(_key['s'])
            click.echo(click.style('Decrypting from 100,000 iterations...', fg='blue'))
            try:
                decoded_s = decrypt(password, s)
                _key['s'] = decoded_s.decode()
            except Exception as e:
                click.echo(click.style('{}'.format(e), fg='red'))

        print(wallet.sign(_key['s'], data.encode()))

    else:
        click.echo(click.style('Keyfile does not exist or data was not provided.', fg='red'))

@_new.command('contract')
@click.argument('code')
@click.argument('name')
@click.argument('stamp_amount')
@click.argument('keyfile')
@click.argument('server_url')
def new_contract(code, name, stamp_amount, keyfile, server_url):
    if not keyfile:
        _key = os.environ['SESSION_KEY']
    else:
        _key = signing_key_for_keyfile(keyfile)
    code = os.path.realpath(code)
    _code = open(code).read()
    contract = tools.build_contract(_code, name, stamp_amount, _key)
    r = tools.submit_contract(contract, server_url)
    print(r.text)

############################################################
# MOCK COMMANDS SUBGROUP
# USED FOR TESTING PURPOSES ONLY
############################################################
@click.group('mock')
def mock():
    pass


@mock.command('contract')
@click.argument('code')
@click.argument('name')
@click.argument('stamp_amount')
@click.argument('keyfile')
def mock_contract(code, name, stamp_amount, keyfile):
    # sender_sk: str, code_str: str, contract_name: str='sample', stamps: int=1.0
    code = os.path.realpath(code)
    _code = open(code).read()

    if not keyfile:
        _key = os.environ['SESSION_KEY']
    else:
        _key = signing_key_for_keyfile(keyfile)

    contract = ContractTransactionBuilder.create_contract_tx(sender_sk=_key,
                                                             code_str=_code,
                                                             contract_name=name,
                                                             gas_supplied=int(stamp_amount))

    s = SenecaClient(sbb_idx=0, num_sbb=0, metering=CilantroConf.STAMPS_ENABLED)
    # make a contract transaction struct
    s.submit_contract(contract)

############################################################
# CONSTITUTION COMMANDS SUBGROUP
# USED FOR CREATING TESTNETS
############################################################
@click.group('constitution')
def constitution():
    pass

@constitution.command('constitution', short_help='Generates constitution for deployment')
@click.option('-t', '--test', 'test', is_flag=True)
@click.argument('filename')
@click.argument('masternodes')
@click.argument('witnesses')
@click.argument('delegates')
def _constitution(filename, masternodes, witnesses, delegates, test=False):
    generate_constitution(filename, int(masternodes), int(witnesses), int(delegates), test=test)


main.add_command(_constitution)
main.add_command(get)
main.add_command(_set)
main.add_command(_new)
main.add_command(mock)
