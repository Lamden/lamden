import unittest
from cilantro.logger import get_logger, overwrite_logger_level


log = get_logger("TestRunner")


PROTOCOL_TESTS = [
    'tests.protocol.structures',
    'tests.protocol.statemachine'

    # TODO -- write tests/ensure existing tests pass for modules below
    # 'tests.protocol.interprets',
    # 'tests.protocol.proofs',
    # 'tests.protocol.reactor',
    # 'tests.protocol.transport',
    # 'tests.protocol.wallets',
    ]

MESSAGE_TESTS = [
    'tests.messages.consensus',
    'tests.messages.envelope',
    'tests.messages.reactor',
    'tests.messages.transactions'
]

OVERLAY_TESTS = [
    'tests.overlay'
]

TESTGROUPS = [
    PROTOCOL_TESTS,
    MESSAGE_TESTS,
    OVERLAY_TESTS
]


if __name__ == '__main__':
    TEST_FLAG = 'S'  # test flag represents failure (F) or success (S) of testing
    loader = unittest.TestLoader()

    all_errors = []

    num_suites, num_success, num_tests = 0, 0, 0

    for group in TESTGROUPS:
        for test in group:

            suite = loader.discover(test)  # finds all unit tests in the testgroup directory
            num_suites += 1
            num_tests += suite.countTestCases()

            runner = unittest.TextTestRunner(verbosity=3)
            log = get_logger("TestRunner")
            test_result = runner.run(suite)

            if test_result.errors:
                for i in range(len(test_result.errors) + 1):
                    all_errors.append(test_result.errors[i])
                    log.error("Error in {} - exiting test framework".format(test))
                    log.error('Number of errors: {}'.format(len(test_result.errors)))
                    log.error('Error in: {}'.format(test_result.errors[i][0]))
                    log.error('Error traceback: {}'.format(test_result.errors[i][1]))
                    TEST_FLAG = 'F'
                    break

            elif test_result.failures:
                for i in range(len(test_result.failures) + 1):
                    all_errors.append(test_result.failures[i])
                    log.error("failure in {} - exiting test framework".format(test))
                    log.error('\nNumber of failures: {}'.format(len(test_result.failures)))
                    log.error(test_result.failures[i][0])
                    log.error(test_result.failures[i][1])
                    TEST_FLAG = 'F'
                    break
            else:
                log.info("\n\nNo errors in {}\n\n".format(test))
                num_success += 1

    for err in all_errors:
        log.error("failure: {}".format(err))

    _l = log.info

    if TEST_FLAG == 'S':
        log.info('\n\n All tests have finished running and passed - testing complete!\n\n')
    elif TEST_FLAG == 'F':
        log.error('\n\n Some tests have finished running and there are errors - check log\n\n')
        _l = log.critical

    _l("{}\{} tests passed.".format(num_tests-len(all_errors), num_tests))
    _l("{}/{} test suites passed.".format(num_suites, num_success))

    # Overwrite logger level to surpress asyncio's whining
    overwrite_logger_level(9000)


