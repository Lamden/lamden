import os
import sys
import argparse
import configparser

def _set_boot_ips(ips, config):
    config['DEFAULT']['boot_ips'] = ips

def _set_ip(ip, config):
    config['DEFAULT']['ip'] = ip

def get_complete_set():
    return

def poll_cache():
    return

def _setup_argparse(p):
    p.add_argument("-i", "--ip", help="The IP address of the node calling the configure script", required=True)
    p.add_argument("-t", "--type", help="The type of node calling the script", choices=["masternode", "delegate", "witness"], required=True)
    p.add_argument("-i", "--index", help="The index of the node calling the script", type=int, required=True)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    _setup_argparse(p)
    args = p.parse_args()

    config_path = 'conf/{}{}/cilantro.conf'.format(args.type, args.index)
    configparser = configparser.ConfigParser()
    config = configparser.read(config_path)

