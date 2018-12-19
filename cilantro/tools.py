import requests
from cilantro.messages.transaction.contract import ContractTransactionBuilder
from cilantro.messages.transaction.container import TransactionContainer
from seneca.engine.interpreter import Seneca, SenecaInterpreter
from seneca.engine.interface import SenecaInterface

def get_contract_state(contract_name, datatype, key, server_url):
    j = {'contract_name': contract_name, 'datatype': datatype, 'key': key}
    r = requests.get('http://{}/state'.format(server_url), json=j)
    return r.json()

def get_contract_meta(contract_name, server_url):
    j = {'contract_name': contract_name}
    r = requests.get('http://{}/contract-meta'.format(server_url), json=j)
    meta = r.json()
    meta.update(parse_code_str(meta['code_str']))
    return meta

def get_block(server_url, block_hash=None, block_number=None):
    j = {'hash': block_hash} if block_hash else {'number': block_number}
    r = requests.get('http://{}/blocks'.format(server_url), json=j)
    return r

def get_transaction(tx_hash, server_url):
    j = {'hash': tx_hash}
    r = requests.get('http://{}/transaction'.format(server_url), json=j)
    return r

def get_transactions(block_hash, server_url):
    j = {'hash': block_hash}
    r = requests.get('http://{}/transactions'.format(server_url), json=j)
    return r

def get_balance(address):
    print(address)

def get_contract(contract_address, server_url):
    j = {'contract': contract_address}
    r = requests.get('http://{}'.format(server_url), json=j)
    return r

def build_contract(code, name, stamp_amount, k):
    contract = ContractTransactionBuilder.create_contract_tx(sender_sk=k,
                                                             code_str=code,
                                                             contract_name=name,
                                                             gas_supplied=int(stamp_amount))
    return contract


def submit_contract(contract, server_url):
    r = requests.post('http://{}/'.format(server_url), data=TransactionContainer.create(contract).serialize())
    return r

def parse_code_str(code_str):
    with SenecaInterface(False) as interface:
        Seneca.exports = {}
        Seneca.imports = {}
        interface.compile_code(code_str)
        datatypes = {}
        exports = []
        for k, v in Seneca.loaded['__main__'].items():
            if v.__class__.__module__ == 'seneca.libs.datatypes':
                datatypes[k] = v
        for k, v in Seneca.exports.items():
            if not k.startswith('seneca.libs'):
                exports.append(k)
        return { 'datatypes': datatypes, 'exports': exports }
