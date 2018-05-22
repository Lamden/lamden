from cilantro.utils import IPUtils
from unittest import TestCase


class TestIPUtils(TestCase):

    def test_get_vk_valid(self):
        vk = 'E532F434E348749B97F371212CDEF69F436AB8D342618AF67D1443808E36DAEF'
        vk_url = 'tcp://{}:7020'.format(vk)

        fetched_vk = IPUtils.get_vk(vk_url)

        self.assertEqual(vk, fetched_vk)

    def test_get_vk_invalid(self):
        fetched_vk = IPUtils.get_vk("tcp://127.0.0.1:8080")

        self.assertEqual(False, fetched_vk)

    def test_interpolate_url(self):
        ip = "127.0.0.1"
        url = "tcp://E532F434E348749B97F371212CDEF69F436AB8D342618AF67D1443808E36DAEF:8080"

        actual_url = IPUtils.interpolate_url(url, ip)
        correct_url = 'tcp://{}:8080'.format(ip)

        self.assertEqual(actual_url, correct_url)