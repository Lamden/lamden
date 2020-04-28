#!/usr/bin/env python3


import unittest
import sys
import time
import os
import re
from cilantro_ee.core.logger import get_logger, overwrite_logger_level
import argparse
from cilantro_ee.utils.factory import _wait_for_mongo, _wait_for_redis

# Hack to import stuff from groups.py regardless of where this file is run
try: from .groups import *
except: from groups import *

"""
This file acts as a single point of entry for runner all unit and integration tests. If this file is run with no args,
all tests are run.
"""

log = get_logger("TestRunner")
delim = '-' * 80
os.environ['__INHERIT_CONSTITUTION__'] = 'False'


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


def _should_skip_module(module_name: str, modules_to_skip: list) -> bool:
    for mod in modules_to_skip:
        if type(mod) is list:
            if _should_skip_module(module_name, mod):
                return True
        elif mod == module_name or mod.startswith(module_name):
            return True
    return False


def skip_circle_ci_modules(module_to_skip='tests/integration'):
    assert os.getenv('CIRCLECI'), 'Not using CIRCLECI, this operation is Dangerous Davis approved'
    total_containers = os.getenv("CIRCLE_NODE_TOTAL")
    container_idx = os.getenv("CIRCLE_NODE_INDEX")
    all_files = []
    for root, dirs, files in os.walk(module_to_skip, topdown=False):
        for name in files:
            if re.search(r'^test_.*.py$', name):
                all_files.append(os.path.join(root, name))
                # if int(container_idx) != idx % int(total_containers):
                #     print('Removing {}...'.format(name))
                #     os.remove(os.path.join(root, name))
    print("All test files (without removing any): {}".format(all_files))
    removes = []
    for i, name in enumerate(all_files):
        if int(container_idx) != i % int(total_containers):
            print("Removing file {}".format(name))
            os.remove(name)
            removes.append(name)

    # Just to see a list of non-removed files for debugging
    for f in removes: all_files.remove(f)
    print("All test files this node is responsible for: {}".format(all_files))


def main(args):
    _wait_for_redis()
    _wait_for_mongo()
    log.debug("\nRunning test suites with args\n\nrun unit tests={}\nrun integration tests={}\nverbosity={}\n"
              "skip modules={}\nskip tests={}\n[env var] CILANTRO_DEBUG={}\n[env var] CI={}\n"
              .format(args.unit, args.integration, args.verbosity, args.skip_modules, args.skip_tests,
                      os.getenv('CILANTRO_DEBUG'), os.getenv('CI')))

    all_tests = []
    if args.unit:
        all_tests += UNIT_TESTS
    if args.integration:
        all_tests += INTEGRATION_TESTS

    if args.integration and os.getenv("CIRCLECI"):
        skip_circle_ci_modules('tests/integration')

    skip_test_names = args.skip_tests

    skip_module_names = args.skip_modules or []
    if os.getenv('CILANTRO_DEBUG'):
        skip_module_names += DEBUG_DISABLED_TESTS
    if os.getenv('CI'):
        skip_module_names += CI_DISABLED_TESTS

    TEST_FLAG = 'S'  # test flag represents failure (F) or success (S) of testing
    loader = unittest.TestLoader()
    all_errors = []
    num_suites, num_success, = 0, 0
    num_tests = -len(skip_test_names) if skip_test_names else 0
    abs_start = time.time()

    for group in all_tests:
        for test in group:

            if _should_skip_module(test, skip_module_names):
                log.notice("Skipping test module {}".format(test))
                continue
            log.info("Starting tests for module {}...".format(test))

            suite = loader.discover(test)  # finds all unit tests in the testgroup directory



            # Skip tests functions specified in command line args
            skip_tests(suite, skip_test_names)

            num_suites += 1
            num_tests += suite.countTestCases()

            # runner = unittest.TextTestRunner(verbosity=3)
            runner = unittest.TextTestRunner(verbosity=0)

            start = time.time()

            # Suppress all log output below logging.WARNING if -v is specified
            if not args.verbosity:
                overwrite_logger_level(9000)  # Set log level to 9000  to suppress most output from tests
            test_result = runner.run(suite)
            overwrite_logger_level(1)  # Change logging level back

            run_time = round(time.time() - start, 3)
            tests_total = suite.countTestCases()
            # test_failures = max(len(test_result.errors), len(test_result.failures))
            test_failures = len(test_result.errors) + len(test_result.failures)
            tests_passed = tests_total - test_failures

            if test_result.errors:
                for i in range(len(test_result.errors)):
                    all_errors.append(test_result.errors[i][0])
                    log.error("Error in {}".format(test))
                    log.error('Number of errors: {}'.format(len(test_result.errors)))
                    log.error('Error #{}: {}'.format(i+1, test_result.errors[i][0]))  # test_result.errors[i][0] = test_retrieve_block_invalid_args (tests.storage.test_blockchain_storage.TestBlockStorageDriver)
                    log.error('Error traceback: \n{}'.format(test_result.errors[i][1]))
                    TEST_FLAG = 'F'

            if test_result.failures:
                for i in range(len(test_result.failures)):
                    all_errors.append(test_result.failures[i][0])
                    log.error("failure in {} - exiting test framework".format(test))
                    log.error('\nNumber of failures: {}'.format(len(test_result.failures)))
                    log.error(test_result.failures[i][0])
                    log.error(test_result.failures[i][1])
                    TEST_FLAG = 'F'

            if not test_result.errors and not test_result.failures:
                _l = log.info
                num_success += 1
            else:
                _l = log.fatal

            _l('\n' + delim + "\nSuite {} completed in {} seconds with {}/{} tests passed.\n"
               .format(test, run_time, tests_passed, tests_total) + delim + '\n')

    total_time = round(time.time() - abs_start, 3)

    if all_errors:
        fails_str = '\n\n' + delim + '\nTEST FAILURES:\n\n'
        for err in all_errors:
            fails_str += str(err) + '\n'
        fails_str += '\n' + delim
        log.error(fails_str)

    result_msg = '\n\n' + delim + "\n\n{}/{} tests passed.".format(num_tests - len(all_errors), num_tests)
    result_msg += "\n{}/{} test suites passed.".format(num_success, num_suites)
    result_msg += "\nTotal run time: {} seconds".format(total_time)
    result_msg += '\n\n' + delim

    _l = log.info if TEST_FLAG == 'S' else log.error
    _l(result_msg)

    if TEST_FLAG == 'S':
        log.success('\n\nAll tests have finished running and passed - testing complete!\n')
        overwrite_logger_level(9000)
        sys.exit(0)
    elif TEST_FLAG == 'F':
        log.fatal('\n\nSome tests have finished running and there are errors - check log\n')
        overwrite_logger_level(9000)
        sys.exit(1)


if __name__ == '__main__':
    args = argparse.ArgumentParser()

    """
    -v or --verbosity

    Optional verbosity. If true, no output from unit/integration tests will be suppressed
    """
    args.add_argument('-v', '--verbosity', action='store_true', help='Optional verbosity. If true, no output from unit/integration tests will be surpressed')

    """
    --unit [0/1]

    Enable/disable unit tests. Default is 1 (enabled)
    """
    args.add_argument("--unit", type=int, default=1, help="Flag to run unit tests. Default is True")

    """
    --integration [0/1]

    Enable/disable integration tests. Default is 1 (enabled)
    """
    args.add_argument("--integration", type=int, default=1, help="Flag to run integration tests. Default is True")

    """
    --skip_tests TestEd25199wallet.test_something_hella_long, SomeOtherModule.some_other_test, ...

    Skip individual test case functions by specifying TestClassName.test_func_name, separated by commas
    """
    args.add_argument("--skip_tests", nargs='+', type=str)

    """
    --skip_modules tests.protocol.wallets, tests.constants, ...

    Skip test modules by specifying a list of modules names separated by commas. Specifying a higher level module will
    skip all submodules, ie. specifying 'tests.protocol' will skip 'tests.protocol.proofs', 'tests.protocol.reactor',
    and any other 'tests.protocol.*'
    """
    args.add_argument("--skip_modules", nargs='+', type=str)

    main(args.parse_args())
