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

    def test_nanos_to_str(self):
        nanos = 1606141759 * 1e9
        self.assertEqual(hlc.nanos_to_iso8601(nanos),'2020-11-23T14:29:19.000000000Z')
        nanos = 1606141759000000001
        self.assertEqual(hlc.nanos_to_iso8601(nanos), '2020-11-23T14:29:19.000000001Z')
        nanos = 1606141759001001001
        self.assertEqual(hlc.nanos_to_iso8601(nanos), '2020-11-23T14:29:19.001001001Z')


    def test_str_to_nanos(self):
        s = '2020-11-23T14:29:19.000000001Z'
        nanos = 1606141759000000001
        self.assertEqual( hlc.iso8601_to_nanos(s), nanos)

        s = '2020-11-23T14:29:19.000000000Z'
        nanos = 1606141759 * 1e9
        self.assertEqual( hlc.iso8601_to_nanos(s), nanos)

        s = '2020-11-23T14:29:19.001001001Z'
        nanos = 1606141759001001001
        self.assertEqual( hlc.iso8601_to_nanos(s), nanos)

        s = '2020-11-23T14:29:19.0011Z'
        nanos = 1606141759001100000
        self.assertEqual( hlc.iso8601_to_nanos(s), nanos)
