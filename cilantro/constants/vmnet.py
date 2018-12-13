import cilantro, ujson as json, random, os
from os.path import join, dirname, exists
from cilantro.logger.base import get_logger
from cilantro.protocol.overlay.ip import ip_to_decimal
from cilantro.protocol.wallet import get_vk
from os import getenv as env

cilantro_path = cilantro.__path__[0]
constituion_dir = join(dirname(cilantro_path), 'vmnet_configs', 'constitutions')
public_dir = join(constituion_dir, 'public')
private_dir = join(constituion_dir, 'private')
test_dir = join(constituion_dir, 'test')
os.makedirs(public_dir, exist_ok=True)
os.makedirs(private_dir, exist_ok=True)
os.makedirs(test_dir, exist_ok=True)

def get_config_file(fname):
    fpath = join(dirname(cilantro_path), 'vmnet_configs', fname)
    assert exists(fpath), '"{}" does not exist'.format(fpath)
    return fpath

def project_path():
    return cilantro.__path__[0]

def _generate_keys(ip=None):
    sk = ('%064x' % random.randrange(32**64))[:64]
    vk = get_vk(sk)
    random.seed()
    keys = { 'sk': sk, 'vk': vk }
    if ip:
        keys.update({'ip': ip})
    return keys

def get_constitution(constitution_json):
    """
        Either use the json as constitution or use GLOBAL_SEED to generate a
        constitution file when testing=True. Otherwise generate a secret SK, VK
        pair for yourself when testing=False.
    """
    log = get_logger(__name__)

    fpath = join(test_dir, constitution_json)
    if not exists(fpath):
        fpath = join(public_dir, constitution_json)

    if constitution_json and exists(fpath):
        log.info('Loading constituion from {}...'.format(fpath))
        with open(fpath) as f:
            return json.loads(f.read())
    else:
        raise Exception('DeploymentErorr: Not testing or deploying as a single node type!')

def generate_constitution(name, masternodes, witnesses, delegates, test=False):
    public_key_file = join(public_dir, name+'.json')
    private_key_file = join(private_dir, name+'.json')
    test_key_file = join(test_dir, name+'.json')
    private_keys = {
        "masternodes": [_generate_keys() for i in range(masternodes)],
        "witnesses": [_generate_keys() for ip in range(witnesses)],
        "delegates": [_generate_keys() for ip in range(delegates)]
    }
    public_keys = {}
    for group in private_keys:
        public_keys[group] = []
        for key in private_keys[group]:
            public_keys[group].append({'vk': key['vk']})
    with open(private_key_file, 'w+') as f:
        f.write(json.dumps(private_keys, indent=4))
    with open(public_key_file, 'w+') as f:
        f.write(json.dumps(public_keys, indent=4))
    if test:
        with open(test_key_file, 'w+') as f:
            f.write(json.dumps(private_keys, indent=4))
