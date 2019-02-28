from cilantro_ee.utils.test.integration_utils.smart_contract_tester import SmartContractTester
from cilantro_ee.logger.base import overwrite_logger_level
import sys


def test_sc_submit(env_path):
    mr_dumpo = SmartContractTester(env_path)
    mr_dumpo.start()


if __name__ == '__main__':
    overwrite_logger_level(11)
    assert len(sys.argv) >= 2, "Expected at least 1 arg -- the path of the environment to use"
    env_path = sys.argv[1]
    test_sc_submit(env_path)
