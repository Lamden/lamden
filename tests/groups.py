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
    'tests.protocol.structures',
    'tests.protocol.statemachine',
    'tests.protocol.wallets',
    'tests.nodes.masternode',

    # TODO -- write tests/ensure existing tests pass for modules below
    # 'tests.protocol.interpreter',
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

OVERLAY_TESTS = [
    'tests.overlay'
]

# All unit tests
UNIT_TESTS = [
    # OVERLAY_TESTS,  # TODO investigate why overlay tests still arent working on the VM
    PROTOCOL_TESTS,
    MESSAGE_TESTS,
    CONSTANTS_TESTS,
]

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