import requests
from cilantro.messages.transaction.contract import ContractTransactionBuilder
from cilantro.messages.transaction.container import TransactionContainer


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
