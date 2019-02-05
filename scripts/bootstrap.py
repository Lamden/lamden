import os, configparser
from cilantro.utils.test.node_runner import *

CONFIG_PATH = '/etc/cilantro.conf'


def main():
    print("BoOoOoOoOoOTSSSSSSRAaaAAAaaaaaaaaaaAAAAAAaaaaaaaaaAAAAAAAAAAaaaaaaaAAAAAaaaaaaaaAAAAAAAAPPpppPP")

    assert os.path.exists(CONFIG_PATH), "No config file found at path {}".format(CONFIG_PATH)
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    config = config['DEFAULT']

    # Some configs are specified as env vars so they can be accessible across multiple files
    if config['ssl_enabled']:
        os.environ['SSL_ENABLED'] = "1"
    os.environ['HOST_IP'] = config['ip']
    os.environ['BOOT_IPS'] = config['boot_ips']
    os.environ['CONSTITUTION_FILE'] = config['constitution_file']

    # print("VKBook mns {}".format(VKBook.get_masternodes()))

    if config['node_type'] == 'witness':
        run_witness(sk=config['sk'], log_lvl=int(config['log_lvl']), reset_db=config['reset_db'])
    elif config['node_type'] == 'delegate':
        run_delegate(sk=config['sk'], log_lvl=int(config['log_lvl']), seneca_log_lvl=int(config['seneca_log_lvl']),
                     reset_db=config['reset_db'])
    elif config['node_type'] == 'masternode':
        run_mn(sk=config['sk'], log_lvl=int(config['log_lvl']), nonce_enabled=config['nonce_enabled'],
               reset_db=config['reset_db'])
    else:
        raise Exception("Unrecognized node type {}".format(config['node_type']))


if __name__ == '__main__':
    main()
