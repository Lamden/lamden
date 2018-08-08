#!/usr/bin/env python3.6
import random
import argparse
import string
import configparser

if __name__ == '__main__':
    random_pw = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(12))

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--username', default='cilantro_user')
    parser.add_argument('--password', default=random_pw)
    parser.add_argument('--database', default='cilantro_dev')
    parser.add_argument('--hostname', default='127.0.0.1')
    parser.add_argument('--output-file', default='./db_conf.ini')
    args = parser.parse_args()

    conf = configparser.RawConfigParser()
    s = 'DB'
    conf.add_section(s)

    for k,v in vars(args).items():
        if k is not 'output_file':
            conf.set(s, k, v)

    with open(args.output_file, 'w') as f:
        conf.write(f)
