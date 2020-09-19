import os
import json

from contracting.client import ContractingClient

DEFAULT_PATH = os.path.dirname(__file__)
DEFAULT_GENESIS_PATH = os.path.dirname(__file__) + '/genesis.json'
DEFAULT_SUBMISSION_PATH = os.path.dirname(__file__) + '/submission.s.py'


# Maintains order and a set of constructor args that can be included in the constitution file
def submit_from_genesis_json_file(client: ContractingClient, filename=DEFAULT_GENESIS_PATH, root=DEFAULT_PATH,
                                  submission_path=DEFAULT_SUBMISSION_PATH, update=False):
    with open(filename) as f:
        genesis = json.load(f)

    for contract in genesis['contracts']:
        c_filepath = root + '/genesis/' + contract['name'] + '.s.py'

        with open(c_filepath) as f:
            code = f.read()

        contract_name = contract['name']
        if contract.get('submit_as') is not None:
            contract_name = contract['submit_as']

        if update:
            client.set_submission_contract(filename=submission_path)
            client.raw_driver.set_contract(
                name=contract_name,
                code=code,
                owner=contract['owner'],
                developer='sys'
            )

        elif client.get_contract(contract_name) is None:
            client.submit(code, name=contract_name, owner=contract['owner'],
                          constructor_args=contract['constructor_args'])


def flush_sys_contracts(client: ContractingClient, filename=DEFAULT_GENESIS_PATH,
                        submission_path=DEFAULT_SUBMISSION_PATH):

    # Resets submission contract, allows for updating
    client.set_submission_contract(filename=submission_path)

    # Iterates through genesis contract files
    with open(filename) as f:
        genesis = json.load(f)

    for contract in genesis['contracts']:
        # Get the name of each
        contract_name = contract['name']
        if contract.get('submit_as') is not None:
            contract_name = contract['submit_as']

        #
        client.raw_driver.delete(f'{contract_name}.__code__')
        client.raw_driver.commit()


def setup_member_contracts(initial_masternodes, initial_delegates, client: ContractingClient, root=DEFAULT_PATH):
    members = root + '/genesis/members.s.py'

    with open(members) as f:
        code = f.read()

    if client.get_contract('masternodes') is None:
        client.submit(code, name='masternodes', owner='election_house', constructor_args={
            'initial_members': initial_masternodes,
            'candidate': 'elect_masternodes'
        })

    if client.get_contract('delegates') is None:
        client.submit(code, name='delegates', owner='election_house', constructor_args={
            'initial_members': initial_delegates,
            'candidate': 'elect_delegates'
        })


def register_policies(client: ContractingClient):
    # add to election house
    election_house = client.get_contract('election_house')

    policies_to_register = [
        'masternodes',
        'delegates',
        'rewards',
        'stamp_cost'
    ]

    for policy in policies_to_register:
        if client.get_var(
            contract='election_house',
            variable='policies',
            arguments=[policy]
        ) is None:
            election_house.register_policy(contract=policy)


def setup_member_election_contracts(client: ContractingClient, masternode_price=100_000, delegate_price=100_000, root=DEFAULT_PATH):
    elect_members = root + '/genesis/elect_members.s.py'

    with open(elect_members) as f:
        code = f.read()

    if client.get_contract('elect_masternodes') is None:
        client.submit(code, name='elect_masternodes', constructor_args={
            'policy': 'masternodes',
            'cost': masternode_price,
        })

    if client.get_contract('elect_delegates') is None:
        client.submit(code, name='elect_delegates', constructor_args={
            'policy': 'delegates',
            'cost': delegate_price,
        })


def setup_genesis_contracts(initial_masternodes, initial_delegates, client: ContractingClient, filename=DEFAULT_GENESIS_PATH, root=DEFAULT_PATH):
    submit_from_genesis_json_file(client=client, filename=filename, root=root)

    setup_member_contracts(
        initial_masternodes=initial_masternodes,
        initial_delegates=initial_delegates,
        client=client
    )

    register_policies(client=client)

    setup_member_election_contracts(client=client)

    client.raw_driver.commit()
    client.raw_driver.clear_pending_state()
