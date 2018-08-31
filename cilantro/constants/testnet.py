# TESTNET_MASTERNODES = [
#     {
#         "sk": "06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a",
#         "vk": "82540bb5a9c84162214c5540d6e43be49bbfe19cf49685660cab608998a65144",
#     }
# ]
#
# TESTNET_WITNESSES = [
#     {
#         "sk": "91f7021a9e8c65ca873747ae24de08e0a7acf58159a8aa6548910fe152dab3d8",
#         "vk": "0e669c219a29f54c8ba4293a5a3df4371f5694b761a0a50a26bf5b50d5a76974",
#     },
#     {
#         "sk": "f9489f880ef1a8b2ccdecfcad073e630ede1dd190c3b436421f665f767704c55",
#         "vk": "50869c7ee2536d65c0e4ef058b50682cac4ba8a5aff36718beac517805e9c2c0",
#     }
# ]
#
# TESTNET_DELEGATES = [
#     {
#         "sk": "8ddaf072b9108444e189773e2ddcb4cbd2a76bbf3db448e55d0bfc131409a197",
#         "vk": "3dd5291906dca320ab4032683d97f5aa285b6491e59bba25c958fc4b0de2efc8",
#     },
#     {
#         "sk": "5664ec7306cc22e56820ae988b983bdc8ebec8246cdd771cfee9671299e98e3c",
#         "vk": "ab59a17868980051cc846804e49c154829511380c119926549595bf4b48e2f85",
#     },
#     {
#         "sk": "20b577e71e0c3bddd3ae78c0df8f7bb42b29b0c0ce9ca42a44e6afea2912d17b",
#         "vk": "0c998fa1b2675d76372897a7d9b18d4c1fbe285dc0cc795a50e4aad613709baf",
#     }
# ]
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
