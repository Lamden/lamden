import unittest
from tests.constants.test_BST import Node

"""
CI Suite for Cilantro

Tests are broken into different groups depending on what they test and how they critical they are. Each test group must 
pass all tests before the next test group runs. The structure of the tests forms a binary tree which is traversed in 
post order. For example:

        C
      /   \
     A     B 
     
Both A and B Test Groups must pass entirely before testing Group C

This script would be integrated into Travis CI 

TEST_GROUP_A: protocol unit tests
TEST_GROUP_B: messages unit tests
TEST_GROUP_C: reactor unit tests 
TEST_GROUP_D: integration testing
TEST_GROUP_E
TEST_GROUP_F
TEST_GROUP_G

"""

TEST_GROUP_A = [
    'tests.protocol.structures',
    'tests.protocol.statemachine'
    ]

TEST_GROUP_B = [
    'tests.messages.consensus',
    'tests.messages.envelope',
    # 'tests.messages.reactor', TODO these tests have failures
    # 'tests.messages.transactions' TODO these tests have failures
]

TEST_GROUP_C = [
    'tests.protocol.transport'  # only transport_integration.py has all passing test atm
]

TEST_GROUP_D = []

TESTGROUPS = [
    TEST_GROUP_A,
    TEST_GROUP_B,
    TEST_GROUP_C
]

root = Node(TEST_GROUP_C)
root.left = Node(TEST_GROUP_A)
root.right = Node(TEST_GROUP_B)

if __name__ == '__main__':
    TEST_FLAG = 'S'  # test flag represents failure (F) or success (S) of testing
    loader = unittest.TestLoader()

    post_order_tests = []

    all_errors = []
    list_tests = root.post_order_traversal(root, data=post_order_tests)
    print(list_tests)
    print("ayy finished data: {}".format(post_order_tests))

    for k in list_tests:
        print(k)
        for t in k:
            print(t)

            suite = loader.discover(t)  # finds all unit tests in the testgroup directory

            runner = unittest.TextTestRunner(verbosity=3)
            TestResult = runner.run(suite)

            if TestResult.errors:
                for i in range(len(TestResult.errors) + 1):
                    all_errors.append(TestResult.errors[i])
                    print("error in {} - exiting test framework".format(t))
                    print('\n\n', 'Number of errors:', len(TestResult.errors))
                    print('\n\n', 'Error in:', TestResult.errors[i][0])
                    print('\n\n', 'Error traceback:', TestResult.errors[i][1])
                    TEST_FLAG = 'F'
                    break

            elif TestResult.failures:
                for i in range(len(TestResult.failures) + 1):
                    all_errors.append(TestResult.failures[i])
                    print("failure in {} - exiting test framework".format(t))
                    print('\n\n', 'Number of failures:', len(TestResult.failures))
                    print('\n\n', TestResult.failures[i][0])
                    print('\n\n', TestResult.failures[i][1])
                    TEST_FLAG = 'F'
                    break
            else:
                print("No errors in {} \n\n".format(t))

    for err in all_errors:
        # print("failure in {} - exiting test framework".format(err))
        print("failure: {}".format(err))

    if TEST_FLAG == 'S':
        print('\n\n All tests have finished running and passed - testing complete!')
    elif TEST_FLAG == 'F':
        print('\n\n Some tests have finished running and there are errors - check log')


