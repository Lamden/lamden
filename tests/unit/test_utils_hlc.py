from unittest import TestCase
from lamden.utils import hlc


class TestUtilsHLC(TestCase):
    def test_nanos_from_hlc_timestamp(self):
        hlc_timestamp = "2022-07-18T17:04:54.967101696Z_0"

        expected_nanos = 1658163894967101696
        self.assertEqual(expected_nanos, hlc.nanos_from_hlc_timestamp(hlc_timestamp=hlc_timestamp))

    def test_nanos_from_hlc_timestamp__invalid_timestmap_returns_zero(self):
        hlc_timestamp = ""

        expected_nanos = 0
        self.assertEqual(expected_nanos, hlc.nanos_from_hlc_timestamp(hlc_timestamp=hlc_timestamp))

    def test_nanos_from_hlc_timestamp__hlc_of_zeros_returns_block_number_0(self):
        hlc_timestamp = "0000-00-00T00:00:00.000000000Z_0"

        expected_nanos = 0

        self.assertEqual(expected_nanos, hlc.nanos_from_hlc_timestamp(hlc_timestamp=hlc_timestamp))

