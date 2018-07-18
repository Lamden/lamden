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
    'tests.protocol.interpreters',
    'tests.protocol.structures',
    'tests.protocol.statemachine',
    'tests.protocol.wallets',
    'tests.nodes.masternode',

    # TODO -- write tests/ensure existing tests pass for modules below
    # 'tests.protocol.proofs',
    # 'tests.protocol.reactor',
    # 'tests.protocol.transport',  # this should break ... so TODO: fix
    ]

MESSAGE_TESTS = [
    'tests.messages.consensus',
    'tests.messages.envelope',
    'tests.messages.reactor',
    'tests.messages.transactions'
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
    'tests.db'
]

SMART_CONTRACT_TESTS = [
    'tests.contracts'
]

"""
I think OVERLAY_TESTS arent working on CI b/c dat boi falcon is trying to open up ports and stuff on a CI container 
... so I think we need to run those tests as integration tests inside a docker container
"""
UNIT_TESTS = [
    # OVERLAY_TESTS,  # TODO see note above
    PROTOCOL_TESTS,
    MESSAGE_TESTS,
    CONSTANTS_TESTS,
    UTIL_TESTS,
    DB_TESTS,
    SMART_CONTRACT_TESTS,
]
# All unit tests

"""
------------------------------------------------------------------------------------------------------------------
                                            Integration Tests
------------------------------------------------------------------------------------------------------------------
"""

NODE_INTEGRATION_TESTS = [
    'tests.nodes.integration'
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
CI_DISABLED_TESTS = OVERLAY_TESTS #+ DB_TESTS + SMART_CONTRACT_TESTS

# Tests that are skipped if the environment variable $CILANTRO_DEBUG is set
DEBUG_DISABLED_TESTS = [] # SMART_CONTRACT_TESTS
