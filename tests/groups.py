"""
This file defines the structure and hierarchy of Cilantro's test suites.

TODO -- better documentation on whats going on here
"""


"""
------------------------------------------------------------------------------------------------------------------
                                                Unit Tests
------------------------------------------------------------------------------------------------------------------
"""

PROTOCOL_TESTS = [
    'tests.unit.protocol.overlay',
    'tests.unit.protocol.structures',
    'tests.unit.protocol.wallets',
    'tests.unit.protocol.multiprocessing',
    'tests.unit.protocol.comm',
    ]

NODE_TESTS = [
    'tests.unit.nodes.masternode',
    'tests.unit.nodes.delegate',
    'tests.unit.nodes.base',
]

MESSAGE_TESTS = [
    'tests.unit.messages.consensus',
    'tests.unit.messages.envelope',
    'tests.unit.messages.transactions',
    'tests.unit.messages.block_data',
    'tests.unit.messages.signals',
]

UTIL_TESTS = [
    'tests.unit.utils'
]

DB_TESTS = [
    'tests.unit.storage'
]

SMART_CONTRACT_TESTS = [
    # 'tests.unit.contracts'
]

# All unit tests
UNIT_TESTS = [
    PROTOCOL_TESTS,
    NODE_TESTS,
    MESSAGE_TESTS,
    UTIL_TESTS,
    DB_TESTS,
    SMART_CONTRACT_TESTS,
]

"""
------------------------------------------------------------------------------------------------------------------
                                            Integration Tests
------------------------------------------------------------------------------------------------------------------
"""

NODE_INTEGRATION_TESTS = [
    'tests.integration.networking',
    'tests.integration.overlay'
]

# All integration tests
INTEGRATION_TESTS = [
    NODE_INTEGRATION_TESTS
]


"""
------------------------------------------------------------------------------------------------------------------
                                            Special Groups
------------------------------------------------------------------------------------------------------------------
"""

# Tests to skip on the CI.
CI_DISABLED_TESTS = []#+ DB_TESTS + SMART_CONTRACT_TESTS

# Tests that are skipped if the environment variable $CILANTRO_DEBUG is set
DEBUG_DISABLED_TESTS = [] # SMART_CONTRACT_TESTS
