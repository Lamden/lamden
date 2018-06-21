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

    print('dat boy is runnin')

    all_errors = []

    num_suites = 0
    num_success = 0

    for group in TESTGROUPS:
        for test in group:

            suite = loader.discover(test)  # finds all unit tests in the testgroup directory
            num_suites += 1

            runner = unittest.TextTestRunner(verbosity=3)
            log = get_logger("TestRunner")
            TestResult = runner.run(suite)

            if TestResult.errors:
                for i in range(len(TestResult.errors) + 1):
                    all_errors.append(TestResult.errors[i])
                    log.error("Error in {} - exiting test framework".format(test))
                    log.error('Number of errors: {}'.format(len(TestResult.errors)))
                    log.error('Error in: {}'.format(TestResult.errors[i][0]))
                    log.error('Error traceback: {}'.format(TestResult.errors[i][1]))
                    TEST_FLAG = 'F'
                    break

            elif TestResult.failures:
                for i in range(len(TestResult.failures) + 1):
                    all_errors.append(TestResult.failures[i])
                    log.error("failure in {} - exiting test framework".format(test))
                    log.error('\nNumber of failures: {}'.format(len(TestResult.failures)))
                    log.error(TestResult.failures[i][0])
                    log.error(TestResult.failures[i][1])
                    TEST_FLAG = 'F'
                    break
            else:
                log.info("\n\nNo errors in {}\n\n".format(test))
                num_success += 1

    for err in all_errors:
        log.info("failure: {}".format(err))

    log.critical("Ran {} test suites with {} successes and {} failures.".format(num_suites, num_success, len(all_errors)))

    if TEST_FLAG == 'S':
        log.info('\n\n All tests have finished running and passed - testing complete!\n\n')
    elif TEST_FLAG == 'F':
        log.critical('\n\n Some tests have finished running and there are errors - check log\n\n')

    # Overwrite logger level to surpress asyncio's whining
    overwrite_logger_level(9000)


