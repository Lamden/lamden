import cilantro
from cilantro.protocol import wallet
import json, os, configparser
import shutil
from copy import deepcopy

OPS_DIR_PATH = os.path.dirname(cilantro.__path__[-1]) + '/ops'
CONST_DIR_PATH = os.path.dirname(cilantro.__path__[-1]) + '/constitutions/public'

BASE_CONFIG_DIR_PATH = OPS_DIR_PATH + '/base'
LIGHT_CONF_PATH = BASE_CONFIG_DIR_PATH + '/circus_light.conf'
FULL_CONF_PATH = BASE_CONFIG_DIR_PATH + '/circus_full.conf'

NAME_MAP = {'masternodes': 'masternode', 'witnesses': 'witness', 'delegates': 'delegate'}


def _generate_constitution(file_name, num_masters, num_witnesses, num_delegates) -> dict:
    def _build_nodes(num_nodes=64) -> list:
        nodes = []
        for i in range(num_nodes):
            sk, vk = wallet.new()
            nodes.append({'sk': sk, 'vk': vk})
        return nodes

    file_path = CONST_DIR_PATH + '/' + file_name
    testnet = {'masternodes': _build_nodes(num_masters), 'witnesses': _build_nodes(num_witnesses),
               'delegates': _build_nodes(num_delegates)}

    # Build a version with only VK's and store this at 'file_path'
    testnet_vk_only = deepcopy(testnet)
    for k in testnet_vk_only:
        for row in testnet_vk_only[k]:
            del row['sk']

    with open(file_path, 'w') as fp:
        json.dump(testnet_vk_only, fp, indent=4)

    return testnet


def _check_constitution_exists(file_name) -> bool:
    return os.path.exists(CONST_DIR_PATH + '/' + file_name)


def _get_input(prompt, skip=False):
    if skip: return 0
    else: return input(prompt + '\n')


def _input_to_bool(str_in: str, default=False) -> bool:
    assert str_in.lower() in ('y', 'n'), "invalid bool input. Must be 'y' or 'n', not {}".format(str_in)
    return True if str_in.lower() == 'y' else False


def _get_bool_input(prompt, skip=False, default=False) -> bool:
    str_in = _get_input(prompt, skip=skip)
    if not str_in:
        return default
    else:
        return _input_to_bool(str_in)


def _get_node_name(node_type: str, node_idx: int):
    assert node_type in NAME_MAP, "unrecognized node type {}".format(node_type)
    return "{}{}".format(NAME_MAP[node_type], node_idx)


def main():
    config_name = _get_input("Enter the name of this configuration (ex cloud-2-2-2)")
    base_config_dir_path = OPS_DIR_PATH + '/environments/' + config_name
    config_dir_path = base_config_dir_path + '/conf'
    const_file = config_name + '.json'

    if os.path.exists(base_config_dir_path):
        if _get_bool_input("WARNING: Environment named {} already exists at path {}. Replace with new one? (y/n)"
                           .format(config_name, base_config_dir_path)):
            shutil.rmtree(base_config_dir_path)
        else:
            return

    num_mn = int(_get_input("Enter number of Masternodes"))
    assert num_mn > 0, "num_mn must be greater than 0"

    num_dels = int(_get_input("Enter number of Delegates"))
    assert num_dels > 0, "num_dels must be greater than 0"

    num_wits = int(_get_input("Enter number of Witnesses"))
    assert num_wits > 0, "num_wits must be greater than 0"

    # Build new constitution file
    if _check_constitution_exists(const_file):
        print("WARNING: Constitution file {} already exists. Replacing with new one.".format(const_file))
    const_dict = _generate_constitution(const_file, num_mn, num_wits, num_dels)

    skip = _get_bool_input("Use default values for rest of config? (y/n)")
    if skip:
        print("Using default values for remaining inputs")

    reset_db = _get_bool_input("Reset DB on all nodes upon boot? (y/n), default='y'", default=True, skip=skip)
    ssl_enabled = _get_bool_input("Enable SSL on Webservers? (y/n), default='y'", skip=skip, default=False)
    nonce_enabled = _get_bool_input("Require nonces for user transactions? (y/n), default='n'", default=False, skip=skip)

    mn_log_lvl = int(_get_input("Enter Masternode log lvl. Must be 0 or in [11, 100]. (default=11)", skip=skip)) or 11
    assert mn_log_lvl >= 0, 'log lvl must be greater than 0'
    assert mn_log_lvl not in range(1, 11), "Masternode log cannot be in range [1, 10]"

    wit_log_lvl = int(_get_input("Enter Witness log lvl. (default=11)", skip=skip)) or 11
    assert wit_log_lvl >= 0, 'log lvl must be greater than 0'

    del_log_lvl = int(_get_input("Enter Delegate log lvl. (default=11)", skip=skip)) or 11
    assert del_log_lvl >= 0, 'log lvl must be greater than 0'

    sen_log_lvl = int(_get_input("Enter Seneca log lvl. (default=11)", skip=skip)) or 11
    assert sen_log_lvl >= 0, 'log lvl must be greater than 0'

    # Now, to actually build the configs...
    os.makedirs(config_dir_path)
    for node_group in const_dict:
        for i, node_info in enumerate(const_dict[node_group]):
            node_name = _get_node_name(node_group, i)
            node_type = NAME_MAP[node_group]

            node_dir = config_dir_path + '/' + node_name
            cilantro_conf_path = node_dir + '/' + 'cilantro.conf'
            circus_conf_path = node_dir + '/' + 'circus.conf'
            os.mkdir(node_dir)

            # Get the general info
            config_info = {'ip': 'TBD',                 # TODO should we just remove this and put it in later?
                           'boot_ips': 'TBD',           # TODO should we just remove this and put it in later?
                           'node_type': node_type,
                           'sk': node_info['sk'],
                           'vk': node_info['vk'],
                           'reset_db': reset_db,
                           'constitution_file': const_file,
                           'ssl_enabled': ssl_enabled,
                           }

            # Set node specific info
            if node_type == 'masternode':
                config_info['nonce_enabled'] = nonce_enabled
                config_info['log_lvl'] = mn_log_lvl
                shutil.copyfile(FULL_CONF_PATH, circus_conf_path)
            elif node_type == 'witness':
                config_info['log_lvl'] = wit_log_lvl
                shutil.copyfile(LIGHT_CONF_PATH, circus_conf_path)
            elif node_type == 'delegate':
                config_info['log_lvl'] = del_log_lvl
                config_info['seneca_log_lvl'] = sen_log_lvl
                shutil.copyfile(LIGHT_CONF_PATH, circus_conf_path)

            # Write the cilantro config file
            config = configparser.ConfigParser()
            config['DEFAULT'] = config_info
            with open(cilantro_conf_path, 'w') as f:
                config.write(f)


    print("-"*64 + "\nDone generating configs for environment named {} at path {}".format(config_name, config_dir_path))


if __name__ == '__main__':
    main()
