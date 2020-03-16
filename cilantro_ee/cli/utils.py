import os
import subprocess
import ipaddress
import cilantro_ee
from checksumdir import dirhash
from contracting.client import ContractingClient
from cilantro_ee.storage.contract import BlockchainDriver


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


def version_reboot():
    pass
    rel = input("Enter Release branch:")

    #cmds = ["cd /Volumes/dev/lamden/cilantro-enterprise", "git fetch", f"git checkout {rel}"]

    #proc = subprocess.Popen(cmds, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    #stdout, stderr = proc.communicate()


def get_update_state():
    driver = BlockchainDriver()
    active_upgrade = driver.get_var(contract='upgrade', variable='upg_lock', mark=False)
    pepper = driver.get_var(contract='upgrade', variable='upg_pepper', mark=False)
    start_time = driver.get_var(contract='upgrade', variable='upg_init_time', mark=False)
    window = driver.get_var(contract='upgrade', variable='upg_window', mark=False)
    mcount = driver.get_var(contract='upgrade', variable='tot_mn', mark=False)
    dcount = driver.get_var(contract='upgrade', variable='tot_dl', mark=False)
    mvotes = driver.get_var(contract='upgrade', variable='mn_vote', mark=False)
    dvotes = driver.get_var(contract='upgrade', variable='dl_vote', mark=False)
    consensus = driver.get_var(contract='upgrade', variable='pepper', mark=False)

    print("Upgrade -> {} Cil Pepper   -> {}\n"
          "Init time -> {}, Time Window -> {}\n"
          "Masters      -> {}\n"
          "Delegates    -> {}\n"
          "MN-Votes     -> {}\n "
          "DL-Votes     -> {}\n "
          "Consensus    -> {}\n"
          .format(active_upgrade, pepper, start_time, window, mcount, dcount,
                  mvotes, dvotes, consensus))
