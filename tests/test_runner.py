import unittest
import sys
import time
from cilantro.logger import get_logger, overwrite_logger_level
import logging


"""
This file acts as a single point of entry for runner all unit and integration tests. If this file is run with no args,
all tests are run.

Options to:
-- run only unit tests
-- omit long running unit tests

-- run only integration tests
"""


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

NODE_INTEGRATION_TESTS = [
    'tests.nodes.integration'
]

TESTGROUPS = [
    # OVERLAY_TESTS,
    PROTOCOL_TESTS,
    MESSAGE_TESTS,
    CONSTANTS_TESTS,
    NODE_INTEGRATION_TESTS,
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

    abs_start = time.time()

    for group in TESTGROUPS:
        for test in group:

            suite = loader.discover(test)  # finds all unit tests in the testgroup directory
            num_suites += 1
            num_tests += suite.countTestCases()

            # runner = unittest.TextTestRunner(verbosity=3)
            runner = unittest.TextTestRunner(verbosity=0)

            start = time.time()

            # overwrite_logger_level(logging.WARNING)  # Set log level to warning to suppress most output from tests
            test_result = runner.run(suite)
            overwrite_logger_level(logging.DEBUG)  # Change logging level back

            run_time = round(time.time() - start, 3)
            tests_total = suite.countTestCases()
            test_failures = max(len(test_result.errors), len(test_result.failures))
            tests_passed = tests_total - test_failures

            _l = log.critical
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
                _l = log.info
                log.info("No errors in {}".format(test))
                num_success += 1

            _l('\n\n' + delim + "\nSuite {} completed in {} seconds with {}/{} tests passed.\n"
               .format(test, run_time, tests_passed, tests_total) + delim + '\n')

    total_time = round(time.time() - abs_start, 3)

    for err in all_errors:
        log.error("failure: " + str(err))

    result_msg = '\n\n' + delim + "\n\n{}/{} tests passed.".format(num_tests - len(all_errors), num_tests)
    result_msg += "\n{}/{} test suites passed.".format(num_success, num_suites)
    result_msg += "\nTotal run time: {} seconds".format(total_time)
    result_msg += '\n\n' + delim

    _l = log.info if TEST_FLAG == 'S' else log.error
    _l(result_msg)

    if TEST_FLAG == 'S':
        log.info('\n\nAll tests have finished running and passed - testing complete!\n')
        overwrite_logger_level(9000)
        sys.exit(0)
    elif TEST_FLAG == 'F':
        log.critical('\n\nSome tests have finished running and there are errors - check log\n')
        overwrite_logger_level(9000)
        sys.exit(1)

    # Overwrite logger level to surpress asyncio's whining
    # overwrite_logger_level(9000)


