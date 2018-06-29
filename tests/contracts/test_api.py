import unittest
from unittest import TestCase
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import SmartContractTestCase
from seneca.execute_sc import execute_contract


log = get_logger("TestAPI")

class TestAPI(SmartContractTestCase):
    def test_enum(self):
        self.run_contract(code_str="""
import some_api
print(some_api.hello())
        """)

if __name__ == '__main__':
    unittest.main()
