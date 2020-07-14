import os
from checksumdir import dirhash
from pathlib import Path
import hashlib

'''
    This files is bunch of util's for 
    - building pepper (to verify and join valid network)
    - 
'''


def build_pepper(pkg_dir_path):
    pepper1 = dirhash(pkg_dir_path, 'sha256', excluded_extensions = ['pyc'])
    contracting_dir_path = pkg_dir_path + '/../../contracting/contracting'
    pepper2 = dirhash(contracting_dir_path, 'sha256', excluded_extensions = ['pyc'])
    pepper = hashlib.sha256( (pepper1 + pepper2).encode('utf-8')).hexdigest()
    print(pepper)
    return pepper


def verify_pkg():
    chk_sum = input("Enter Pepper to verify:" )
    pepper = build_pepper(pkg_dir_path = os.environ.get('CIL_PATH'))
    if chk_sum == pepper:
        return True
    else:
        return False


def run_test():
    # TODO this is hook to test directory to sun sanity test on package being distributed
    pass


def pkg_ops(arg):
    switcher = {
        1: build_pepper(pkg_dir_path = os.environ.get('CIL_PATH')),
        2: verify_pkg(),
        3: run_test()
    }

    print(switcher.get(arg, "Invalid operation"))


if __name__ == '__main__':
    CURR_DIR = Path(os.getcwd())
    os.environ['PKG_ROOT'] = str(CURR_DIR.parent)
    os.environ['CIL_PATH'] = os.environ.get('PKG_ROOT') #+ '/cilantro'

    print(os.environ.get('CIL_PATH'))

    print("Choose number for Package operation")
    print("1: Generate pepper")
    print("2: Verify Package")
    print("3: Verify current pepper hash")
    choice = input("Enter Package operation: ")
    choice = int(choice)

    pkg_ops(choice)