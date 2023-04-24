from lamden.utils.retrieve_ips import IPFetcher, URLS
from unittest import TestCase
import requests
import asyncio


class TestMigrateBlocksDir(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.external_ip = requests.get('https://ipv4.icanhazip.com').text.strip()


    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.ip_fetcher = IPFetcher()

        # If this first assert fails then replace the URL with another from the URLS const in lamden.utils.external_ip
        # and remove this failing URL from that list as we shouldn't use it anymore if it is flakey
        self.external_ip = self.__class__.external_ip
        self.assertTrue(self.ip_fetcher.is_valid_ip(self.external_ip))

    def tearDown(self):
        pass

    def test_METHOD_get_ip_external__gets_an_ip_using_the_list_of_URLS(self):
        ip_address = self.loop.run_until_complete(self.ip_fetcher.get_ip_external())

        self.assertEqual(self.external_ip, ip_address)

    def test_METHOD_get_ip_from_url__all_URLS_are_still_valid(self):
        for url in URLS:
            print(f'trying {url}')
            ip_address = self.loop.run_until_complete(self.ip_fetcher.get_ip_from_url(url=url))

            self.assertEqual(self.external_ip, ip_address)

    def test_METHOD_get_ip_local_system__can_get_local_system_ip(self):
        local_ip = self.ip_fetcher.get_ip_local_system()
        self.assertTrue(self.ip_fetcher.is_valid_ip(local_ip))


