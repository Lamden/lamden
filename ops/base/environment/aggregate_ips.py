import os
import argparse
import time
import configparser

my_path = os.path.dirname(os.path.abspath(__file__))
cache_path = os.path.join(my_path, '.cache')

def _setup_argparse(p):
    p.add_argument("-i", "--ip", help="The IP address of the node calling the configure script", required=True)
    p.add_argument("-t", "--type", help="The type of node calling the script", choices=["masternode", "delegate", "witness"], required=True)
    p.add_argument("-i", "--index", help="The index of the node calling the script", type=int, required=True)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    _setup_argparse(p)
    args = p.parse_args()

    # Get and save relevant file paths for later reuse in the script
    ip_file = os.path.join(cache_path, "{}{}_ip".format(args.type, args.ip))
    cilantro_config = os.path.join(my_path, 'config/{}{}/cilantro.conf'.format(args.type, args.ip))

    # Write my IP
    with open(ip_file, "w+") as f:
        f.write(args.ip)

    # Find out who I should be waiting for
    _, dirnames, _ = next(os.walk(os.path.join(my_path, 'conf')))
    ip_files = [ '{}_ip'.format(x) for x in dirnames ]
    
    # Wait for everyone else
    all_found = False
    while not all_found:
        _, _, filenames = next(os.walk(cache_path))
        all_found = [ x for x in ip_files if x not in filenames ] == []

    # Get all ips
    all_ips = []
    for ipf in ip_files:
        with open(os.path.join(cache_path, ipf), "r") as f:
            ips.append(f.readline.rstrip())

    # Write my config
    config = ConfigParser()
    config.read(cilantro_config)
    config = config['DEFAULT']
    config['ip'] = args.ip
    config['boot_ips'] = ",".join(ips)
