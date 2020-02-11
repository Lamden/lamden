import argparse
import os
from pathlib import Path


def main(mode = False):
    if mode:
        print("Debug ON")
        return
    else:
        print("Debug Off")


    # setup Env

    os.environ['PKG_PATH'] = Path(os.getcwd())
    os.environ['CIL_ROOT'] = os.getenv('PKG_PATH') + 'cilantro_ee'

    # make data dir
    os.environ['DATADIR'] = ''
    os.environ['NW_CONST'] = ''
    os.environ['BOOT_IP'] = ''
    os.environ['CONFIG_PATH'] = ''
    os.environ['REDIS_CONF'] = ''
    os.environ['LOGS_DIR'] = ''
    os.environ[''] = ''

    # Run setup scripts

    print(os.environ)


if __name__ == "__main__":
    # execute only if run as a script
    parser = argparse.ArgumentParser(description='Node Setup')
    parser.add_argument('debug', type = bool, help='skip post install setup steps')
    parser.print_help()
    args = parser.parse_args()
    main(args.mode)
