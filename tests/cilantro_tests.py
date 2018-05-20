import unittest

"""
CI Suite for Cilantro

Tests are broken into different groups depending on what they test and how they critical they are. Each test group must 
pass all tests before the next test group runs.

This script would be integrated into Travis CI 

TEST_GROUP_A: protocol unit tests
TEST_GROUP_B: messages unit tests
TEST_GROUP_C: reactor unit tests 
TEST_GROUP_D: integration testing
x
x
x

"""

TEST_GROUP_A = [
    'tests.protocol.structures'
    ]

TEST_GROUP_B = [
    'tests.messages.consensus',
    'tests.messages.envelope',
    'tests.messages.reactor',
    'tests.messages.transactions'
]

TEST_GROUP_C = []

TEST_GROUP_D = []

TESTGROUPS = [
    TEST_GROUP_A,
    TEST_GROUP_B
]

if __name__ == '__main__':
    TEST_FLAG = 'S'  # test flag represents failure (F) or success (S) of testing
    for g in TESTGROUPS:
        for t in g:
            loader = unittest.TestLoader()

            suite = loader.discover(t)  # finds all unit tests in the testgroup directory

            runner = unittest.TextTestRunner(verbosity=3)
            TestResult = runner.run(suite)

            if TestResult.errors:
                print("error in {} - exiting test framework".format(t))
                print('\n\n', TestResult.errors)
                print('\n\n', TestResult.failures)
                TEST_FLAG = 'F'
                break
            else:
                print("No errors in {} \n\n".format(t))

    if TEST_FLAG == 'S':
        print('\n\n All tests have finished running and passed - testing complete!')
    elif TEST_FLAG == 'F':
        print('\n\n Some tests have finished running and there are errors - check log')


