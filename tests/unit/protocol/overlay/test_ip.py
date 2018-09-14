import unittest, cilantro
from unittest import TestCase
from unittest.mock import patch
from cilantro.protocol.overlay.ip import *
from os.path import exists, dirname

class TestIP(TestCase):
    def setUp(self):
        pass

    @patch('requests.get')
    def test_get_public_ip_failed(self, requests_get):
        def mock_req(*args, **kwargs):
            raise Exception()

        requests_get.side_effect = mock_req
        with self.assertRaises(Exception) as context:
            get_public_ip()

    def test_get_public_ip(self):
        self.assertIsNotNone(get_public_ip(), 'cannot find public ip, make sure you have internet')

    def test_decimal_to_ip(self):
        self.assertEqual(decimal_to_ip(2130904064), '127.3.4.0')

    def test_ip_to_decimal(self):
        self.assertEqual(ip_to_decimal('127.3.4.0'), 2130904064)

    def test_get_subnet(self):
        self.assertEqual(get_subnet('127.3.4.5'), '127.3.4')

    def test_truncate_ip(self):
        self.assertEqual(truncate_ip('127.3.4.5'), ip_to_decimal('127.3.4.0'))

    def test_get_local_range(self):
        self.assertEqual(get_local_range('1.2.3.4'), (ip_to_decimal('1.2.3.0'), ip_to_decimal('1.2.4.0')))

    def test_get_subnets_range(self):
        self.assertEqual(get_subnets_range('1.2.3.4'), (ip_to_decimal('1.2.0.0'), ip_to_decimal('1.3.0.0')))

    # def test_get_region_range(self):
    #     public_ip = get_public_ip()
    #     module_path = dirname(cilantro.__file__)
    #     data_path = '{}/protocol/overlay/data'.format(module_path)
    #     self.assertEqual(len(get_region_range(public_ip, recalculate=True)), 11)
    #     self.assertTrue(exists('{}/world.csv'.format(data_path)), 'does not have the world\'s IPs')
    #     self.assertTrue(exists('{}/neighborhood.txt'.format(data_path)), 'did not generate the neighbor\'s IPs file')

    def test_get_region_range_no_recalc(self):
        public_ip = get_public_ip()
        module_path = dirname(cilantro.__file__)
        data_path = '{}/protocol/overlay/data'.format(module_path)
        self.assertEqual(len(get_region_range(public_ip)), 11)
        self.assertTrue(exists('{}/world.csv'.format(data_path)), 'does not have the world\'s IPs')
        self.assertTrue(exists('{}/neighborhood.txt'.format(data_path)), 'did not generate the neighbor\'s IPs file')

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
