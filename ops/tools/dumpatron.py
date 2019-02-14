from cilantro.logger.base import get_logger
from cilantro.utils.test.god import God
from cilantro.constants.system_config import *
import sys, os, glob

log = get_logger('Dumpatron')


SSL_ENABLED = False  # TODO make this infered instead of a hard coded flag
VOLUME = TRANSACTIONS_PER_SUB_BLOCK * NUM_SB_PER_BLOCK * NUM_BLOCKS  # Number of transactions to dump


def get_mn_ips(env_path) -> dict:
    assert os.path.exists(env_path + '.cache'), "No .cache dir found at path {}.cache".format(env_path)

    mn_files = glob.glob("{}.cache/ip_masternode*".format(env_path))
    # log.important("got mn files {}".format(mn_files))

    ips = {}

    for mn_file in mn_files:
        with open(mn_file, 'r') as f:
            ips[mn_file[-1]] = f.read()

    return ips


def get_mn_urls_from_ips(ips: dict) -> list:
    # TODO properly detect if this config has SSL enabled. For now we assume it doesnt
    urls = []
    for ip in ips.values():
        if SSL_ENABLED:
            urls.append("https://{}".format(ip))
        else:
            urls.append("http://{}:8080".format(ip))
    return urls


def start_dump(env_path):
    assert os.path.exists(env_path), "No env configs found at path {}".format(env_path)

    mn_ips = get_mn_ips(env_path)
    mn_urls = get_mn_urls_from_ips(mn_ips)
    God.mn_urls = mn_urls
    God.multi_master = True

    log.notice("Set God's MN URLS to {}".format(God.mn_urls))

    log.info("Starting the dump....")

    while True:
        user_input = input("Enter an integer representing the # of transactions to dump, or 'x' to quit. "
                           "Press enter to dump 2 blocks\n")

        if user_input.lower() == 'x':
            log.important("Termination input detected. Breaking")
            break

        vol = int(user_input) if user_input.isdigit() else VOLUME
        log.important3("Dumpatron dumping {} transactions!".format(vol))
        God._dump_it(volume=vol)


if __name__ == '__main__':
    print("dumpatron dump")

    assert len(sys.argv) == 2, "Expected 1 arg -- the path of the environment to use"
    env_path = sys.argv[1]

    start_dump(env_path)