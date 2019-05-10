import glob
from contracting.db.driver import ContractDriver


def contract_name_from_file_path(p):
    directories = p.split('/')
    filename = directories[-1]

    name_and_file_extention = filename.split('.')
    name = name_and_file_extention[0]

    return name


def sync_genesis_contracts():
    # Direct database writing of all contract files in the 'genesis' folder
    d = ContractDriver()

    genesis_contracts = glob.glob('./genesis/*.s.py')
    for contract in genesis_contracts:
        name = contract_name_from_file_path(contract)

        if d.get_contract(name) is None:

            with open(contract) as f:
                contract = f.read()

            d.set_contract(name=name,
                           code=contract,
                           author='sys')
