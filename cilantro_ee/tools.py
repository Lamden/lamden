import requests
from cilantro_ee.messages.transaction.contract import ContractTransactionBuilder
from cilantro_ee.messages.transaction.container import TransactionContainer


def get_contract_state(contract_name, datatype, key, server_url):
    j = {'contract_name': contract_name, 'datatype': datatype, 'key': key}
    r = requests.get('http://{}/state'.format(server_url), json=j)
    return r.json()


def get_contract_meta(contract_name, server_url):
    j = {'contract_name': contract_name}
    r = requests.get('http://{}/contract-meta'.format(server_url), json=j)
    meta = r.json()
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

