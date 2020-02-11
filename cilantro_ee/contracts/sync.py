import glob
import os
from contracting.client import ContractingClient
import cilantro_ee
import json


# need to refactor this code of vkbook
PUBLIC_JSON_DIR = os.path.dirname(cilantro_ee.__path__[-1]) + '/constitutions/public'


def read_public_constitution(filename) -> dict:
    fpath = PUBLIC_JSON_DIR + '/' + filename
    assert os.path.exists(fpath), "No public constitution file found at path {}".format(fpath)
    with open(fpath) as f:
        return json.load(f)


def contract_name_from_file_path(p: str) -> str:
    directories = p.split('/')
    filename = directories[-1]

    name_and_file_extention = filename.split('.')
    name = name_and_file_extention[0]

    return name


def contracts_for_directory(path, extension, directory=os.path.dirname(__file__)):
    dir_path = os.path.join(directory, path) + '/' + extension
    contracts = glob.glob(dir_path)
    return contracts


def sync_genesis_contracts(genesis_path: str='genesis',
                           extension: str='*.s.py',
                           exclude=['vkbook'],
                           directory=os.path.dirname(__file__)):

    # Direct database writing of all contract files in the 'genesis' folder
    # direct_contracts = contracts_for_directory(direct_path, extension)
    # explicitly submit the submission contract
    submission_file = directory + '/submission.s.py'
    client = ContractingClient(submission_filename=submission_file)

    genesis_contracts = contracts_for_directory(genesis_path, extension, directory=directory)

    for contract in genesis_contracts:
        name = contract_name_from_file_path(contract)
        if name in exclude:
            continue

        if client.raw_driver.get_contract(name) is None:
            with open(contract) as f:
                code = f.read()

            client.submit(code, name=name)


def submit_contract_with_construction_args(name, directory=os.path.dirname(__file__), args={}):
    file = directory + '/genesis/{}.s.py'.format(name)

    submission_file = os.path.dirname(__file__) + '/submission.s.py'
    client = ContractingClient(submission_filename=submission_file)

    with open(file) as f:
        code = f.read()
        client.submit(code, name=name, constructor_args=args)

    client.raw_driver.commit()


def submit_vkbook(vkbook_args: dict, overwrite=False):
    if not overwrite:
        c = ContractingClient()
        contract = c.get_contract('vkbook')
        if contract is not None:
            return

    submit_contract_with_construction_args('vkbook', args=vkbook_args)


def extract_sub_dict_values(book, key):
    if key in book:
        sb = book[key]
        vk_list = sb['vk_list'] if 'vk_list' in sb else []
        num_vks = len(vk_list)
        min_quorum = sb['min_quorum'] if 'min_quorum' in sb else num_vks
        if min_quorum > num_vks:
            min_quorum = num_vks
    else:
        vk_list = []
        min_quorum = 0
    return vk_list, min_quorum
  

def extract_vk_args(book):
    book['masternodes'], book['masternode_min_quorum'] = \
                              extract_sub_dict_values(book, 'masternodes')
    book['delegates'], book['delegate_min_quorum'] = \
                              extract_sub_dict_values(book, 'delegates')
    book['witnesses'], book['witness_min_quorum'] = \
                              extract_sub_dict_values(book, 'witnesses')
    book['notifiers'], book['notifier_min_quorum'] = \
                              extract_sub_dict_values(book, 'notifiers')
    book['schedulers'], book['scheduler_min_quorum'] = \
                              extract_sub_dict_values(book, 'schedulers')



# Maintains order and a set of constructor args that can be included in the constitution file
def submit_from_genesis_json_file(filename, client=ContractingClient(), root=os.path.dirname(__file__)):
    with open(filename) as f:
        genesis = json.load(f)

    for contract in genesis['contracts']:
        c_filepath = root + '/genesis/' + contract['name'] + '.s.py'

        with open(c_filepath) as f:
            code = f.read()

        contract_name = contract['name']
        if contract.get('submit_as') is not None:
            contract_name = contract['submit_as']

        client.submit(code, name=contract_name, owner=contract['owner'],
                      constructor_args=contract['constructor_args'])


def submit_node_election_contracts(initial_masternodes, boot_mns, initial_delegates, boot_dels, master_price=100_000,
                                   delegate_price=100_000, root=os.path.dirname(__file__), client=ContractingClient()):
    members = root + '/genesis/members.s.py'

    with open(members) as f:
        code = f.read()

    client.submit(code, name='masternodes', owner='election_house', constructor_args={
        'initial_members': initial_masternodes,
        'minimum': boot_mns,
        'candidate': 'elect_masternodes'
    })

    client.submit(code, name='delegates', owner='election_house', constructor_args={
        'initial_members': initial_delegates,
        'minimum': boot_dels,
        'candidate': 'elect_delegates'
    })

    # add to election house
    election_house = client.get_contract('election_house')
    try:
        election_house.register_policy(contract='masternodes')
    except:
        pass

    try:
        election_house.register_policy(contract='delegates')
    except:
        pass

    try:
        election_house.register_policy(contract='rewards')
    except Exception:
        pass

    try:
        election_house.register_policy(contract='stamp_cost')
    except:
        pass

    elect_members = root + '/genesis/elect_members.s.py'

    with open(elect_members) as f:
        code = f.read()

    client.submit(code, name='elect_masternodes', constructor_args={
        'policy': 'masternodes',
        'cost': master_price,
    })

    client.submit(code, name='elect_delegates', constructor_args={
        'policy': 'delegates',
        'cost': delegate_price,
    })