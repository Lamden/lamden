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
    'tests.protocol.interpreter',
    'tests.protocol.structures',
    'tests.protocol.states',
    'tests.protocol.wallets'
    ]

NODE_TESTS = [
    'tests.nodes.masternode',
    'tests.nodes.delegate',
]

MESSAGE_TESTS = [
    'tests.messages.consensus',
    'tests.messages.envelope',
    'tests.messages.reactor',
    'tests.messages.transactions',
    'tests.messages.block_data',
]

CONSTANTS_TESTS = [
    'tests.constants'
]

UTIL_TESTS = [
    'tests.utils'
]

OVERLAY_TESTS = [
    'tests.overlay'
]

DB_TESTS = [
    'tests.storage'
]

SMART_CONTRACT_TESTS = [
    'tests.contracts'
]

# All unit tests
UNIT_TESTS = [
    OVERLAY_TESTS,
    NODE_TESTS,
    PROTOCOL_TESTS,
    MESSAGE_TESTS,
    CONSTANTS_TESTS,
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
    'tests.nodes.integration',
    'tests.protocol.transport'
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
CI_DISABLED_TESTS = []#[OVERLAY_TESTS] #+ DB_TESTS + SMART_CONTRACT_TESTS

# Tests that are skipped if the environment variable $CILANTRO_DEBUG is set
DEBUG_DISABLED_TESTS = [OVERLAY_TESTS] # SMART_CONTRACT_TESTS
