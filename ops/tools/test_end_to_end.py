from cilantro.utils.test.dumpatron import DumpatronTester
import unittest
import requests
import sys


# class TestEndToEnd(unittest.TestCase):
#
#     def test_end_to_end_bish(self):
#         pass

def test_end_to_end(env_path):
    mr_dumpo = DumpatronTester(env_path)

    print('huh')


if __name__ == '__main__':
    # unittest.main()
    assert len(sys.argv) >= 2, "Expected at least 1 arg -- the path of the environment to use"
    env_path = sys.argv[1]
    test_end_to_end(env_path)
