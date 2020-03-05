import os
import ipaddress
from checksumdir import dirhash


def validate_ip(address):
    try:
        ip = ipaddress.ip_address(address)
        print('%s is a correct IP%s address.' % (ip, ip.version))
        return ip
    except ValueError:
        print('address/netmask is invalid: %s' % address)


def build_pepper(pkg_dir_path=os.environ.get('CIL_PATH')):

    if pkg_dir_path is None:
        pkg_dir_path = '/Volumes/dev/lamden/cilantro-enterprise'

    pepper = dirhash(pkg_dir_path, 'sha256', excluded_extensions = ['pyc'])
    print(pepper)
    return pepper


def verify_cil_pkg(pkg_hash):
    current_pepper = build_pepper(pkg_dir_path = os.environ.get('CIL_PATH'))

    if current_pepper == pkg_hash:
        return True
    else:
        return False
