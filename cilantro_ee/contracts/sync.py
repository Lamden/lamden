import glob
import os
from contracting.client import ContractingClient


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


def sync_genesis_contracts(genesis_path: str='genesis',
                           extension: str='*.s.py'):

    # Direct database writing of all contract files in the 'genesis' folder
    # direct_contracts = contracts_for_directory(direct_path, extension)
    # explicitly submit the submission contract
    submission_file = os.path.dirname(__file__) + '/submission.s.py'
    client = ContractingClient(submission_filename=submission_file)

    genesis_contracts = contracts_for_directory(genesis_path, extension)

    for contract in genesis_contracts:
        name = contract_name_from_file_path(contract)

        if client.raw_driver.get_contract(name) is None:
            print(client.raw_driver.get_contract(name))
            with open(contract) as f:
                code = f.read()

            client.submit(code, name=name)


def submit_contract_with_construction_args(name, args={}):
    file = os.path.dirname(__file__) + '/genesis/{}.s.py'.format(name)

    submission_file = os.path.dirname(__file__) + '/submission.s.py'
    client = ContractingClient(submission_filename=submission_file)

    with open(file) as f:
        code = f.read()

        client.submit(code, name=name, constructor_args=args)
