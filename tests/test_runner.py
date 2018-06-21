import unittest
from cilantro.logger import get_logger




PROTOCOL_TESTS = [
    'tests.protocol.structures',
    'tests.protocol.statemachine'
    ]

MESSAGE_TESTS = [
    'tests.messages.consensus',
    'tests.messages.envelope',
    # 'tests.messages.reactor', TODO these tests have failures
    # 'tests.messages.transactions' TODO these tests have failures
]


TESTGROUPS = [
    PROTOCOL_TESTS,
    MESSAGE_TESTS
]


if __name__ == '__main__':
    TEST_FLAG = 'S'  # test flag represents failure (F) or success (S) of testing
    loader = unittest.TestLoader()

    all_errors = []

    for group in TESTGROUPS:
        for test in group:

            suite = loader.discover(test)  # finds all unit tests in the testgroup directory

            runner = unittest.TextTestRunner(verbosity=3)
            log = get_logger("TestRunner")
            TestResult = runner.run(suite)

            if TestResult.errors:
                for i in range(len(TestResult.errors) + 1):
                    all_errors.append(TestResult.errors[i])
                    print("error in {} - exiting test framework".format(test))
                    print('\n\n', 'Number of errors:', len(TestResult.errors))
                    print('\n\n', 'Error in:', TestResult.errors[i][0])
                    print('\n\n', 'Error traceback:', TestResult.errors[i][1])
                    TEST_FLAG = 'F'
                    break

            elif TestResult.failures:
                for i in range(len(TestResult.failures) + 1):
                    all_errors.append(TestResult.failures[i])
                    print("failure in {} - exiting test framework".format(test))
                    print('\n\n', 'Number of failures:', len(TestResult.failures))
                    print('\n\n', TestResult.failures[i][0])
                    print('\n\n', TestResult.failures[i][1])
                    TEST_FLAG = 'F'
                    break
            else:
                print("No errors in {} \n\n".format(test))

    for err in all_errors:
        # print("failure in {} - exiting test framework".format(err))
        print("failure: {}".format(err))

    if TEST_FLAG == 'S':
        print('\n\n All tests have finished running and passed - testing complete!')
    elif TEST_FLAG == 'F':
        print('\n\n Some tests have finished running and there are errors - check log')


