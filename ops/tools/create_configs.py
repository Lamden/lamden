import cilantro
from cilantro.protocol import wallet
import json, os, configparser
from copy import deepcopy


OPS_DIR_PATH = os.path.dirname(cilantro.__path__[-1]) + '/ops'
CONST_DIR_PATH = os.path.dirname(cilantro.__path__[-1]) + '/constitutions/public'


def generate_testnet_json(file_path, num_masters, num_witnesses, num_delegates) -> dict:
    def _build_nodes(num_nodes=64, prefix='node') -> list:
        nodes = []

        for i in range(num_nodes):
            sk, vk = wallet.new()
            nodes.append({'sk': sk, 'vk': vk})

        return nodes

    def build_masternodes(num_nodes=64):
        return _build_nodes(num_nodes=num_nodes, prefix='masternode')

    def build_witnesses(num_nodes=256):
        return _build_nodes(num_nodes=num_nodes, prefix='witness')

    def build_delegate(num_nodes=32):
        return _build_nodes(num_nodes=num_nodes, prefix='delegate')

    testnet = {'masternodes': build_masternodes(num_masters), 'witnesses': build_witnesses(num_witnesses),
               'delegates': build_delegate(num_delegates)}

    # Build a version with only VK's and store this at 'file_path'
    testnet_vk_only = deepcopy(testnet)

    for k in testnet_vk_only:
        for row in testnet_vk_only[k]:
            del row['sk']

    print("testnet with vk only:\n{}".format(testnet_vk_only))  # TODO remove

    with open(file_path, 'w') as fp:
        json.dump(testnet_vk_only, fp, indent=4)

    return testnet


def _get_input(prompt, skip=False):
    if skip:
        return 0
    else:
        return input(prompt)


def main():
    config_name = input("Enter the name of this configuration (ex cloud-2-2-2)")

    num_mn = int(input("Enter number of Masternodes"))
    assert num_mn > 0, "num_mn must be greater than 0"

    num_dels = int(input("Enter number of Delegates"))
    assert num_dels > 0, "num_dels must be greater than 0"

    num_wits = int(input("Enter number of Witnesses"))
    assert num_wits > 0, "num_wits must be greater than 0"

    # TODO create config files here
    testnet_dict = generate_testnet_json()

    skip = input("Use default values for rest of config? (y/n)") or 'n'
    if skip.lower() == 'y':
        skip = True
        print("Using default values for remaining inputs")
    else:
        skip = False

    reset_db = _get_input("Reset DB on all nodes upon boot? (y/n), default='y'", skip=skip) or 'y'
    assert reset_db.lower() in ('y', 'n'), "invalid reset_db val. Must be 'y' or 'n'"
    reset_db = True if reset_db.lower() == 'y' else False

    ssl_enabled = _get_input("Enable SSL on Webservers? (y/n), default='y'", skip=skip) or 'y'
    assert ssl_enabled.lower() in ('y', 'n'), "invalid ssl_enabled val. Must be 'y' or 'n'"
    ssl_enabled = True if ssl_enabled.lower() == 'y' else False

    nonce_enabled = _get_input("Require nonces for user transactions? (y/n), default='n'", skip=skip) or 'n'
    assert nonce_enabled.lower() in ('y', 'n'), "invalid nonce_enabled val. Must be 'y' or 'n'"
    nonce_enabled = True if nonce_enabled.lower() == 'y' else False

    mn_log_lvl = _get_input("Enter Masternode log lvl. Must be 0 or in [11, 100]. (default=11)", skip=skip) or 11
    assert mn_log_lvl >= 0, 'log lvl must be greater than 0'
    assert mn_log_lvl not in range(1, 11), "Masternode log cannot be in range [1, 10]"

    wit_log_lvl = int(_get_input("Enter Witness log lvl.) (default=11)", skip=skip)) or 11
    assert wit_log_lvl >= 0, 'log lvl must be greater than 0'

    del_log_lvl = int(_get_input("Enter Delegate log lvl). (default=11)", skip=skip)) or 11
    assert del_log_lvl >= 0, 'log lvl must be greater than 0'

    sen_log_lvl = int(_get_input("Enter Seneca log lvl. )(default=11)", skip=skip)) or 11
    assert sen_log_lvl >= 0, 'log lvl must be greater than 0'


if __name__ == '__main__':
    main()