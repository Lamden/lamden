import glob
import os
from contracting.db.driver import ContractDriver
from contracting.compilation.compiler import ContractingCompiler

def contract_name_from_file_path(p: str) -> str:
    directories = p.split('/')
    filename = directories[-1]

    name_and_file_extention = filename.split('.')
    name = name_and_file_extention[0]

    return name


def sync_genesis_contracts(d: ContractDriver,
                           genesis_path: str='genesis',
                           direct_path: str='direct',
                           extension: str='*.s.py',
                           author: str='sys'):

    # Direct database writing of all contract files in the 'genesis' folder
    direct_glob = os.path.join(os.path.dirname(__file__), direct_path) + '/' + extension
    direct_contracts = glob.glob(direct_glob)

    for contract in direct_contracts:
        name = contract_name_from_file_path(contract)

        if d.get_contract(name) is None:

            with open(contract) as f:
                contract = f.read()

            d.set_contract(name=name,
                           code=contract,
                           author=author)
            d.commit()

    genesis_glob = os.path.join(os.path.dirname(__file__), genesis_path) + '/' + extension
    genesis_contracts = glob.glob(genesis_glob)

    compiler = ContractingCompiler()

    for contract in genesis_contracts:
        name = contract_name_from_file_path(contract)

        if d.get_contract(name) is None:

            with open(contract) as f:
                contract = f.read()

            compiled_code = compiler.parse_to_code(contract, lint=True)

            d.set_contract(name=name,
                           code=compiled_code,
                           author=author)
            d.commit()