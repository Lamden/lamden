import subprocess

from checksumdir import dirhash
from lamden import storage
from lamden.logger.base import get_logger
import lamden
import contracting
import os
import importlib
import sys
import secrets
import json
import hashlib
from functools import partial


def reload_module(module_name: str):
    for name, module in sys.modules.items():
        if name.startswith(module_name):
            importlib.reload(module)


class UpgradeManager:
    def __init__(self, state: storage.StateManager, wallet=None, node_type=None, constitution_filename=None, webserver_port=18080, testing=False):
        self.state = state
        self.enabled = state
        self.log = get_logger('UPGRADE')

        self.node_type = node_type
        self.constitution_filename = constitution_filename
        self.webserver_port = webserver_port
        self.wallet = wallet

        self.get = partial(self.state.client.get_var, contract='upgrade', variable='upgrade_state')

        self.locked = self.get(arguments=['locked'])
        self.consensus = self.get(arguments=['consensus'])

        self.cilantro_branch_name = self.get(arguments=['cilantro_branch_name'])
        self.contracting_branch_name = self.get(arguments=['contracting_branch_name'])

        self.pepper = self.get(arguments=['pepper'])

        self.votes = self.get(arguments=['votes'])
        self.voters = self.get(arguments=['voters'])

        self.upgrade = False
        self.testing = testing
        self.testing_flag = False

    def refresh(self):
        self.locked = self.get(arguments=['locked'])
        self.consensus = self.get(arguments=['consensus'])

        self.cilantro_branch_name = self.get(arguments=['cilantro_branch_name'])
        self.contracting_branch_name = self.get(arguments=['contracting_branch_name'])

        self.pepper = self.get(arguments=['pepper'])

    def version_check(self, constitution={}):
        self.refresh()

        enabled = self.state.client.get_contract('upgrade') is not None
        if enabled:
            self.log.info(f'{self.votes}/{self.voters} nodes voted for the upgrade.')

            # check for vote consensys
            if self.consensus:
                if self.testing:
                    self.testing_flag = True
                    self.reset_contract_variables()
                    return

                self.log.info(f'Rebooting Node with new verions: '
                              f'CIL -> {self.cilantro_branch_name}, CON -> {self.contracting_branch_name}')

                cil_path = os.path.dirname(lamden.__file__)

                self.log.info(f'CIL_PATH={cil_path}')
                self.log.info(f'CONTRACTING_PATH={os.path.dirname(contracting.__file__)}')

                old_branch_name = get_version()
                old_contract_name = get_version(os.path.join(os.path.dirname(contracting.__file__), '..'))
                only_contract = self.cilantro_branch_name == old_branch_name
                if self.contracting_branch_name == old_contract_name and self.cilantro_branch_name == old_branch_name:
                    self.log.info(f'New verions is already installed')
                else:
                    self.log.info(f'Old CIL branch={old_branch_name}, '
                                  f'Old contract branch={old_contract_name}, '
                                  f' Only contract update={only_contract}')

                    if version_reboot(self.cilantro_branch_name, self.contracting_branch_name, only_contract):
                        p = build_pepper2()
                        if self.pepper != p:
                            self.log.error(f'peppers mismatch: {self.pepper} != {p}')
                            self.log.error(f'Restore previous versions: {old_branch_name} -> {old_contract_name}')

                            version_reboot(old_branch_name, old_contract_name, only_contract)
                            self.reset_contract_variables()
                        else:
                            self.log.info('Pepper OK. restart new version')

                            self.upgrade = True
                            run_install(only_contract)

                            self.reset_contract_variables()

                            if not self.testing:
                                self.restart_node(constitution=constitution)

                            self.log.info(f'New branch {self.cilantro_branch_name} was reloaded OK.')
                            self.upgrade = False

                    else:
                        self.log.error(f'Update failed. Old branches restored.')
                        version_reboot(old_branch_name, old_contract_name)
                        self.reset_contract_variables()

                    # Restart goes here

                self.reset_contract_variables()

    def reset_contract_variables(self):
        self.log.info('Upgrade process has concluded.')

        self.state.client.raw_driver.driver.set('upgrade.upgrade_state:consensus', None)
        self.state.client.raw_driver.driver.set('upgrade.upgrade_state:locked', False)

        self.log.info('Reset upgrade contract variables.')

    def restart_node(self, constitution):
        for k, v in constitution['masternodes'].items():
            v = v.split(':')[1].lstrip('//')
            constitution['masternodes'][k] = v

        for k, v in constitution['delegates'].items():
            v = v.split(':')[1].lstrip('//')
            constitution['delegates'][k] = v

        # Write the constitution
        constitution_file = f'/tmp/{secrets.token_hex(32)}.json'
        with open(constitution_file, 'w') as f:
            json.dump(constitution, f)

        self_pid = os.getpid()

        args = [
            'cil', 'start', self.node_type, '-k', self.wallet.signing_key, '-c', constitution_file, '-wp',
            str(self.webserver_port), '-p', str(self_pid), '-b', 'true'
        ]

        subprocess.check_call(args)


def build_pepper(pkg_dir_path=os.path.dirname(lamden.__file__)):
    if pkg_dir_path is None:
        pkg_dir_path = '../../lamden'

    pepper = dirhash(pkg_dir_path, 'sha256', excluded_extensions=['pyc'])
    return pepper


def build_pepper2():
    path1 = build_pepper(os.path.dirname(lamden.__file__))
    path2 = build_pepper(os.path.dirname(contracting.__file__))
    pepper2 = hashlib.sha256((path1 + path2).encode('utf-8')).hexdigest()
    return pepper2


def verify_cil_pkg(pkg_hash):
    current_pepper = build_pepper2()

    if current_pepper == pkg_hash:
        return True
    else:
        return False


def run(*args):
    return subprocess.check_call(['git'] + list(args))


def run_install(only_contract=False):
    if not only_contract:
        path = os.path.join(os.path.dirname(lamden.__file__), '..')
        os.chdir(f'{path}')
        subprocess.check_call(['python3', "setup.py", "develop"])  # "install"

    path2 = os.path.join(os.path.dirname(contracting.__file__),  '..')
    os.chdir(f'{path2}')
    return subprocess.check_call(['python3', "setup.py", "develop"])  # "install"


def get_version(path = os.path.join(os.path.dirname(lamden.__file__), '..')):
    cur_branch_name = None
    try:
        os.chdir(path)
        cur_branch_name = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).rstrip().decode()
    except OSError as err:
        print("OS error: {0}".format(err))
    except:
        print("Unexpected error:", sys.exc_info())
    return cur_branch_name


def version_reboot(new_branch_name, new_contract_name='dev', contract_only=False):
    try:
        if not contract_only:
            path = os.path.join(os.path.dirname(lamden.__file__), '..')
            os.chdir(path)

            rel = new_branch_name  # input("Enter New Release branch:")
            br = f'{rel}'
            run("fetch", "--all")
            run("reset", "--hard", f"origin/{br}")

        path2 =  os.path.join(os.path.dirname(contracting.__file__), '..')
        os.chdir(path2)
        run("fetch", "--all")
        run("reset", "--hard", f"origin/{new_contract_name}")

    except OSError as err:
        print("OS error: {0}".format(err))
        return False
    except:
        print("Unexpected error:", sys.exc_info())
        return False

    return True
