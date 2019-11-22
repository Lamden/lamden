import checksumdir
import hashlib

'''
    This files is bunch of util's for 
    - building pepper (to verify and join valid network)
    - 
'''


def build_pepper(pkg_dir_path = None, type= 'sha256'):
    # TODO currently we check all the files under distro it should be binary package in future
    pepper = checksumdir.dirhash(pkg_dir_path, 'sha256', excluded_extensions = ['pyc'])
    print(pepper)
    return pepper

