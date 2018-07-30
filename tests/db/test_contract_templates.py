import unittest
from unittest import TestCase
from cilantro.db.templating import ContractTemplate


class TestContractTemplates(TestCase):

    def test_interpolate_template(self):
        expected_code = \
"""
import rbac
rbac.create_user('davis', 'god')
print("created user named {} with role {}".format('davis', 'god'))
"""
        actual_code = ContractTemplate.interpolate_template('rbac', user='davis', role='god')

        self.assertEqual(expected_code.strip(), actual_code)

if __name__ == '__main__':
    unittest.main()
