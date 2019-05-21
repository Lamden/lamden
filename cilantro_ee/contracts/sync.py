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


def contracts_for_directory(path, extension):
    dir_path = os.path.join(os.path.dirname(__file__), path) + '/' + extension
    contracts = glob.glob(dir_path)
    return contracts


def submit_files(contracts, _compile=True, lint=True, author='sys'):
    compiler = ContractingCompiler()
    driver = ContractDriver()

    for contract in contracts:
        name = contract_name_from_file_path(contract)

        if driver.get_contract(name) is None:
            with open(contract) as f:
                contract = f.read()

            if _compile:
                contract = compiler.parse_to_code(contract, lint=lint)

            driver.set_contract(name=name,
                           code=contract,
                           author=author)
            driver.commit()


def sync_genesis_contracts(genesis_path: str='genesis',
                           direct_path: str='direct',
                           extension: str='*.s.py'):

    # Direct database writing of all contract files in the 'genesis' folder
    direct_contracts = contracts_for_directory(direct_path, extension)
    submit_files(direct_contracts, _compile=False)

    genesis_contracts = contracts_for_directory(genesis_path, extension)
    submit_files(genesis_contracts)
