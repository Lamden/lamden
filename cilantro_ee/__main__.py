import argparse
import os

def main(mode = False):
    if mode:
        print("Debug ON")
        return
    else:
        print("Debug Off")

    # setup Env

    os.environ['CIL_ROOT'] = ''
    os.environ['DATADIR'] = ''
    os.environ['NW_CONST'] = ''
    os.environ['BOOT_IP'] = ''
    os.environ['CONFIG_PATH'] = ''

    pass


if __name__ == "__main__":
    # execute only if run as a script
    parser = argparse.ArgumentParser(description = 'Node Setup')
    parser.add_argument('debug', type = bool,help = 'skip post install setup steps')
    parser.print_help()
    args = parser.parse_args()
    main(args.mode)