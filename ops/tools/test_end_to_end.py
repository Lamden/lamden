from cilantro.utils.test.dumpatron import CurrencyTester
from cilantro.logger.base import overwrite_logger_level
import sys


def test_end_to_end(env_path):
    mr_dumpo = CurrencyTester(env_path)
    mr_dumpo.start()


if __name__ == '__main__':
    overwrite_logger_level(11)
    assert len(sys.argv) >= 2, "Expected at least 1 arg -- the path of the environment to use"
    env_path = sys.argv[1]
    test_end_to_end(env_path)
