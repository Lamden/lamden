from cilantro_ee.core.logger import get_logger
import json
from deprecated.test import get_testnet_json_path

TESTNET_JSON_PATH = get_testnet_json_path()
log = get_logger("TestnetBuilder")


# DEBUG -- TODO DELETE
# print("\n\n\n\n\n TESTNET JSON PATH: {} \n\n\n\n\n".format(TESTNET_JSON_PATH))
# END DEBUG


_MASTERNODES = None
_WITNESSES = None
_DELEGATES = None

TESTNET_MASTERNODES = []
TESTNET_WITNESSES = []
TESTNET_DELEGATES = []

r = None  # Replication Factor


def set_testnet_nodes():
    global _MASTERNODES, _DELEGATES, _WITNESSES, TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES, \
        MN_WITNESS_MAP, WITNESS_MN_MAP, r

    with open(TESTNET_JSON_PATH, 'r') as f:
        _dat_good_json = json.load(f)

    _MASTERNODES = _dat_good_json['masternodes']
    _WITNESSES = _dat_good_json['witnesses']
    _DELEGATES = _dat_good_json['delegates']
    assert len(_WITNESSES) % len(
        _MASTERNODES) == 0, "# of witnesses must be divisible by # of masternodes, but got {} ma" \
                            "sternodes and {} witnesses".format(len(_MASTERNODES), len(_WITNESSES))

    TESTNET_MASTERNODES = [{'sk': node['sk'], 'vk': node['vk']} for node in _MASTERNODES]
    TESTNET_WITNESSES = [{'sk': node['sk'], 'vk': node['vk']} for node in _WITNESSES]
    TESTNET_DELEGATES = [{'sk': node['sk'], 'vk': node['vk']} for node in _DELEGATES]

    r = len(_WITNESSES) // len(_MASTERNODES)  # replication factor
    MN_WITNESS_MAP = {}  # Map of masternodes --> responsible witness set
    WITNESS_MN_MAP = {}  # inverse of map above

    # Build MN_WITNESS_MAP/WITNESS_MN_MAP
    for i, mn in enumerate(_MASTERNODES):
        mn_vk = mn['vk']
        witnesses = [node['vk'] for node in _WITNESSES[i * r:i * r + r]]

        MN_WITNESS_MAP[mn_vk] = witnesses
        for w in witnesses:
            WITNESS_MN_MAP[w] = mn_vk


def get_testnet_nodes():
    global _MASTERNODES, _DELEGATES, _WITNESSES, TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES, \
        MN_WITNESS_MAP, WITNESS_MN_MAP, r

    with open(TESTNET_JSON_PATH, 'r') as f:
        _dat_good_json = json.load(f)

    _MASTERNODES = _dat_good_json['masternodes']
    _WITNESSES = _dat_good_json['witnesses']
    _DELEGATES = _dat_good_json['delegates']
    assert len(_WITNESSES) % len(
        _MASTERNODES) == 0, "# of witnesses must be divisible by # of masternodes, but got {} ma" \
                            "sternodes and {} witnesses".format(len(_MASTERNODES), len(_WITNESSES))

    TESTNET_MASTERNODES = [{'sk': node['sk'], 'vk': node['vk']} for node in _MASTERNODES]
    TESTNET_WITNESSES = [{'sk': node['sk'], 'vk': node['vk']} for node in _WITNESSES]
    TESTNET_DELEGATES = [{'sk': node['sk'], 'vk': node['vk']} for node in _DELEGATES]

    r = len(_WITNESSES) // len(_MASTERNODES)  # replication factor
    MN_WITNESS_MAP = {}  # Map of masternodes --> responsible witness set
    WITNESS_MN_MAP = {}  # inverse of map above

    # Build MN_WITNESS_MAP/WITNESS_MN_MAP
    for i, mn in enumerate(_MASTERNODES):
        mn_vk = mn['vk']
        witnesses = [node['vk'] for node in _WITNESSES[i * r:i * r + r]]

        MN_WITNESS_MAP[mn_vk] = witnesses
        for w in witnesses:
            WITNESS_MN_MAP[w] = mn_vk

    return TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES



set_testnet_nodes()
