import os
import requests
from cilantro.messages.transaction.contract import ContractTransactionBuilder
from cilantro.messages.transaction.container import TransactionContainer


def get_block(server_url, block_hash, block_number):
    j = {'hash': block_hash} if hash else {'number': block_number}
    r = requests.get('http://{}/blocks'.format(server_url), json=j)
    return r


def get_transaction(server_url, tx_hash):
    j = {'hash': tx_hash}
    r = requests.get('http://{}/transaction'.format(server_url), json=j)
    return r


def get_transactions(server_url, block_hash):
    j = {'hash': block_hash}
    r = requests.get('http://{}/transactions'.format(server_url), json=j)
    return r


def get_balance(address):
    print(address)


def get_contract(server_url, contract_address):
    j = {'contract': contract_address}
    r = requests.get('http://{}'.format(server_url), json=j)
    return r


def build_contract(code, name, stamp_amount, k):
    code = os.path.realpath(code)
    _code = open(code).read()

    contract = ContractTransactionBuilder.create_contract_tx(sender_sk=k,
                                                             code_str=_code,
                                                             contract_name=name,
                                                             gas_supplied=int(stamp_amount))

    return contract


def submit_contract(server_url, contract):
    r = requests.post('http://{}/'.format(server_url), data=TransactionContainer.create(contract).serialize())
    return r
