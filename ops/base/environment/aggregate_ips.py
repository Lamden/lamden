import os
import argparse
import time
import configparser
import json

my_path = os.path.dirname(os.path.abspath(__file__))
cache_path = os.path.join(my_path, '.cache')

def _setup_argparse(p):
    p.add_argument("--ip", help="The IP address of the node calling the configure script", required=True)
    p.add_argument("--type", help="The type of node calling the script", choices=["masternode", "delegate", "witness"], required=True)
    p.add_argument("--index", help="The index of the node calling the script", type=int, required=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    _setup_argparse(p)
    args = p.parse_args()

    # Get and save relevant file paths for later reuse in the script
    ip_file = os.path.join(cache_path, "ip_{}{}".format(args.type, args.index))
    cilantro_ee_config = os.path.join(my_path, 'conf/{}{}/cilantro_ee.conf'.format(args.type, args.index))

    # Write my IP
    with open(ip_file, "w+") as f:
        f.write(args.ip)

    # Find out who I should be waiting for
    _, dirnames, _ = next(os.walk(os.path.join(my_path, 'conf')))
    ip_files = [ 'ip_{}'.format(x) for x in dirnames ]
    
    # Wait for everyone else
    all_found = False
    while not all_found:
        _, _, filenames = next(os.walk(cache_path))
        all_found = [ x for x in ip_files if x not in filenames ] == []

    # Sleep for one second to prevent the files being opened before everyone has had the chance
    # to write their IPs
    time.sleep(1)

    # Get all ips
    all_ips = []
    for ipf in ip_files:
        with open(os.path.join(cache_path, ipf), "r") as f:
            all_ips.append(f.readline().rstrip())

    # Write my config'contracts': {0},

    config = configparser.ConfigParser()
    config.read(cilantro_ee_config)
    instanceip = config.set('DEFAULT', 'ip', args.ip)
    bootips = config.set('DEFAULT', 'boot_ips', ",".join(sorted(all_ips)))
    with open(cilantro_ee_config, "w") as cf:
        config.write(cf)

    # nap while everyone writes their IPs to their respective cilantro_ee.conf files
    time.sleep(1)

    # Write the vk_ip_map.json file which contains maps VK --> IP
    # First, we walk the directories and collect the vk and ip information from the cilantro_ee.conf files
    vk_ip = {}
    for _, dirnames, _ in os.walk(os.path.join(my_path, 'conf')):
        for d in dirnames:
            conf_file = os.path.join(my_path, 'conf/{}/cilantro_ee.conf'.format(d))
            assert os.path.exists(conf_file), "No conf file found at path {}".format(conf_file)

            config = configparser.ConfigParser()
            config.read(conf_file)
            vk_ip[config['DEFAULT']['vk']] = config['DEFAULT']['ip']

    assert len(vk_ip) == len(ip_files), "ya done goofed davis\nvk_ip: {}\nip_files: \n".format(vk_ip, ip_files)

    # print("\n\n\n WE GOT VK IP DICT:\n{}\n\n\n".format(vk_ip))
    # Now actually write the file...
    vk_json = os.path.join(my_path, 'conf/{}{}/vk_ip_map.json'.format(args.type, args.index))
    with open(vk_json, "w") as json_file:
        json.dump(vk_ip, json_file)

