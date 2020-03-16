import os
import subprocess
import ipaddress
#  import cilantro_ee
from checksumdir import dirhash
# from contracting.client import ContractingClient


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


# def get_update_state(self):
#     self.client = ContractingClient(driver=self.driver,
#                                     submission_filename=cilantro_ee.contracts.__path__[0] + '/submission.s.py')
#     self.version_state = self.client.get_contract('upgrade')
#
#     self.active_upgrade = self.version_state.quick_read('upg_lock')
#     pepper = self.version_state.quick_read('pepper')
#     self.mn_votes = self.version_state.quick_read('mn_vote')
#     self.dl_votes = self.version_state.quick_read('dl_vote')
#     consensus = self.version_state.quick_read('upg_consensus')
#
#     print("Cil Pepper   -> {}"
#           "Masters      -> {}"
#           "Delegates    -> {}"
#           "Votes        -> {}"
#           "MN-Votes     -> {}"
#           "DL-Votes     -> {}"
#           "Consensus    -> {}"
#           .format(pepper, self.tol_mn, self.tot_dl, self.all_votes, self.mn_votes, self.dl_votes, consensus))
