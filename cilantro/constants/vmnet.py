import cilantro, ujson as json, random
from os.path import join, dirname, exists
from cilantro.logger.base import get_logger
from cilantro.protocol.overlay.ip import ip_to_decimal
from cilantro.protocol.wallet import get_vk
from os import getenv as env

cilantro_path = cilantro.__path__[0]

def get_config_file(fname):
    fpath = join(dirname(cilantro_path), 'vmnet_configs', fname)
    assert exists(fpath), '"{}" does not exist'.format(fpath)
    return fpath

def project_path():
    return cilantro.__path__[0]

def get_constitution(constitution_json=None):
    """
        Either use the json as constitution or use GLOBAL_SEED to generate a
        constitution file when testing=True. Otherwise generate a secret SK, VK
        pair for yourself when testing=False.
    """
    log = get_logger(__name__)

    def _generate_keys(ip):
        assert env('GLOBAL_SEED'), 'No GLOBAL_SEED found.'
        random.seed(int(env('GLOBAL_SEED'), 16)+ip_to_decimal(ip))
        sk = '%64x' % random.randrange(16**64)
        vk = get_vk(sk)
        random.seed()
        return { 'sk': sk, 'vk': vk, 'ip': ip }


    if env('TEST_NAME') or env('__TEST__'):
        log.important('ConstitutionWarning: This is for testing purposes only!')
        fpath = join(dirname(cilantro_path), 'testnet_configs', constitution_json or '')
        if constitution_json and exists(fpath):
            log.info('Loading constituion from {}...'.format(fpath))
            with open(fpath) as f:
                return json.loads(f.read())
        else:
            log.info('Generating constitution...')
            return {
                "masternodes": [_generate_keys(ip) for ip in env('MASTERNODE', '').split(',') if ip != ''],
                "witnesses": [_generate_keys(ip) for ip in env('WITNESS', '').split(',') if ip != ''],
                "delegates": [_generate_keys(ip) for ip in env('DELEGATE', '').split(',') if ip != '']
            }
    elif env('NODE_TYPE'):
        log.important('Deploying as a {}'.format(env('NODE_TYPE')))
        return {
            "masternodes": [],
            "witnesses": [],
            "delegates": []
        }
    else:
        raise Exception('DeploymentErorr: Not testing or deploying as a single node type!')
