import json, math
from cilantro.utils.test.testnet_nodes import TESTNET_JSON_PATH


with open(TESTNET_JSON_PATH, 'r') as f:
    _dat_good_json = json.load(f)

_MASTERNODES = _dat_good_json['masternodes']
_WITNESSES = _dat_good_json['witnesses']
_DELEGATES = _dat_good_json['delegates']
assert len(_WITNESSES) % len(_MASTERNODES) == 0, "# of witnesses must be divisible by # of masternodes, but got {} ma" \
                                                 "sternodes and {} witnesses".format(len(_MASTERNODES), len(_WITNESSES))

MAJORITY = math.ceil(len(_DELEGATES) * 2/3)

TESTNET_MASTERNODES = [{'sk': node['sk'], 'vk': node['vk']} for node in _MASTERNODES]
TESTNET_WITNESSES = [{'sk': node['sk'], 'vk': node['vk']} for node in _WITNESSES]
TESTNET_DELEGATES = [{'sk': node['sk'], 'vk': node['vk']} for node in _DELEGATES]

r = len(_WITNESSES) // len(_MASTERNODES)  # replication factor
MN_WITNESS_MAP = {}  # Map of masternodes --> responsible witness set
WITNESS_MN_MAP = {}  # inverse of map above

for i, mn in enumerate(_MASTERNODES):
    mn_vk = mn['vk']
    witnesses = [node['vk'] for node in _WITNESSES[i*r:i*r+r]]

    MN_WITNESS_MAP[mn_vk] = witnesses
    for w in witnesses:
        WITNESS_MN_MAP[w] = mn_vk
