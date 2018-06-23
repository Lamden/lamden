import unittest
import sys
import time
from cilantro.logger import get_logger, overwrite_logger_level


log = get_logger("TestRunner")

delim = '-' * 40

PROTOCOL_TESTS = [
    'tests.protocol.structures',
    'tests.protocol.statemachine',

    # TODO -- write tests/ensure existing tests pass for modules below
    # 'tests.protocol.interpreter',
    # 'tests.protocol.proofs',
    # 'tests.protocol.reactor',
    # 'tests.protocol.transport',  # this should break ... so TODO: fix
    'tests.protocol.wallets',
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

TESTGROUPS = [
    PROTOCOL_TESTS,
    MESSAGE_TESTS,
    CONSTANTS_TESTS,
    # OVERLAY_TESTS
]


if __name__ == '__main__':
    # TODO -- implement args to ...
    """
    TODO -- implement args to...
        - break on first failure, or continue
        - thing 2
    """
    TEST_FLAG = 'S'  # test flag represents failure (F) or success (S) of testing
    loader = unittest.TestLoader()

    all_errors = []

    num_suites, num_success, num_tests = 0, 0, 0

    for group in TESTGROUPS:
        for test in group:

            suite = loader.discover(test)  # finds all unit tests in the testgroup directory
            num_suites += 1
            num_tests += suite.countTestCases()

            # runner = unittest.TextTestRunner(verbosity=3)
            runner = unittest.TextTestRunner(verbosity=0)
            log = get_logger("TestRunner")

            start = time.time()
            test_result = runner.run(suite)
            end = time.time()

            run_time = round(end - start, 3)
            tests_total = suite.countTestCases()
            suite_failures = len(test_result.errors) + len(test_result.failures)
            tests_passed = tests_total - suite_failures

            if test_result.errors:
                for i in range(len(test_result.errors)):
                    all_errors.append(test_result.errors[i])
                    log.error("Error in {}".format(test))
                    log.error('Number of errors: {}'.format(len(test_result.errors)))
                    log.error('Error #{}: {}'.format(i+1, test_result.errors[i][0]))
                    log.error('Error traceback: {}'.format(test_result.errors[i][1]))
                    TEST_FLAG = 'F'

            elif test_result.failures:
                for i in range(len(test_result.failures)):
                    all_errors.append(test_result.failures[i])
                    log.error("failure in {} - exiting test framework".format(test))
                    log.error('\nNumber of failures: {}'.format(len(test_result.failures)))
                    log.error(test_result.failures[i][0])
                    log.error(test_result.failures[i][1])
                    TEST_FLAG = 'F'

            else:
                log.info("No errors in {}".format(test))
                num_success += 1

            log.info('\n\n' + delim + "\nSuite {} completed in {} seconds with {}/{} tests passed.\n"
                     .format(test, run_time, tests_passed, tests_total) + delim + '\n')

    for err in all_errors:
        log.error("failure: " + str(err))

    _l = log.info if TEST_FLAG == 'F' else log.critical

    result_msg = '\n\n' + delim + "\n\n{}\{} tests passed.".format(num_tests - len(all_errors), num_tests)
    result_msg += "\n{}/{} test suites passed.".format(num_suites, num_success)
    result_msg += '\n\n' + delim
    _l(result_msg)

    if TEST_FLAG == 'S':
        log.info('\nAll tests have finished running and passed - testing complete!\n')
        sys.exit(0)
    elif TEST_FLAG == 'F':
        log.critical('\nSome tests have finished running and there are errors - check log\n')
        _l = log.error
        sys.exit(1)

    # Overwrite logger level to surpress asyncio's whining
    overwrite_logger_level(9000)


