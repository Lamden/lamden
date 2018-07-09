import unittest
import sys
import time
from cilantro.logger import get_logger, overwrite_logger_level
import logging
import argparse

# Hack to import stuff from groups.py regardless of where this file is run
try: from .groups import *
except: from groups import *

"""
This file acts as a single point of entry for runner all unit and integration tests. If this file is run with no args,
all tests are run.

Options to:
-- run only unit tests
-- omit long running unit tests

-- run only integration tests
"""

log = get_logger("TestRunner")
delim = '-' * 80


def skip_tests(test_suite: unittest.TestSuite, test_names: list):
    if not test_names:
        return

    for name in test_names:
        split = name.split('.')
        assert len(split) == 2, "Invalid test name {} ... test names must be specified as TestClassName.test_name,\
                                ie TestSomeClass.test_some_func".format(name)

    _skip_tests(test_suite, test_names)

def _skip_tests(test_suite: unittest.TestSuite, test_names: list):
    for t in test_suite:
        if isinstance(t, unittest.TestCase):
            _apply_skips(t, test_names)
        else:
            _skip_tests(t, test_names)

def _apply_skips(test_case: unittest.TestCase, test_names: list):
    def split_test_name(name):
        split = name.split('.')
        return split[0], split[1]

    # TODO we make this more efficient/pretty by precomputing a module_name: test_names(list) mapping
    for module_name, test_name in map(split_test_name, test_names):
        if module_name == type(test_case).__name__:
            for func in dir(test_case):
                if func == test_name:
                    setattr(test_case, func, unittest.skip('skip specified in command line args')(getattr(test_case, func)))
                    break


def main(args):
    log.debug("\nRunning test suites with flags:\n\n\trun unit tests={}\n\trun integration tests={}\n\tverbosity={}\n\tskip tests={}\n"
              .format(args.unit, args.integration, args.verbosity, args.skip))

    all_tests = []
    if args.unit:
        all_tests += UNIT_TESTS
    if args.integration:
        all_tests += INTEGRATION_TESTS
    skip_test_names = args.skip

    TEST_FLAG = 'S'  # test flag represents failure (F) or success (S) of testing
    loader = unittest.TestLoader()
    all_errors = []
    num_suites, num_success, = 0, 0
    num_tests = -len(skip_test_names) if skip_test_names else 0
    abs_start = time.time()

    for group in all_tests:
        for test in group:

            suite = loader.discover(test)  # finds all unit tests in the testgroup directory

            # Skip tests specified in command line args
            skip_tests(suite, skip_test_names)

            num_suites += 1
            num_tests += suite.countTestCases()

            # runner = unittest.TextTestRunner(verbosity=3)
            runner = unittest.TextTestRunner(verbosity=0)

            start = time.time()

            if not args.verbosity:
                overwrite_logger_level(logging.WARNING)  # Set log level to warning to suppress most output from tests
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


if __name__ == '__main__':
    args = argparse.ArgumentParser()

    # -v or --verbosity: Optional verbosity. If true, no output from unit/integration tests will be surpressed
    args.add_argument('-v', '--verbosity', action='store_true', help='Optional verbosity. If true, no output from unit/integration tests will be surpressed')

    # --unit_tests [0/1]: Optional unit tests. Default is 1
    args.add_argument("--unit", type=int, default=1, help="Flag to run unit tests. Default is True")

    #  --integration_tests [0/1]: Optional integration tests. Default is 1
    args.add_argument("--integration", type=int, default=1, help="Flag to run integration tests. Default is True")

    # --skip_tests TestEd25199Wallet.test_something_hella_long, ... : Skip tests by specifying TestClassName.ModuleName,
    # seperated by commas
    args.add_argument("--skip", nargs='+', type=str)

    main(args.parse_args())

