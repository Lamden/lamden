import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import socket

URLS = [
    "https://icanhazip.com/",
    "https://ident.me/",
    "https://ifconfig.me/ip",
    "https://ipinfo.io/ip"
]


class IPFetcher:
    def __init__(self, urls=URLS):
        self.urls = urls

    def fetch(self, url):
        try:
            response = requests.get(url, timeout=5)
            return response.text.strip()
        except Exception as e:
            print(f"Error fetching IP from {url}: {e}")
            return None

    def is_valid_ip(self, ip):
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    async def get_ip_external(self):
        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor() as executor:
            tasks = [loop.run_in_executor(executor, self.fetch, url) for url in self.urls]

            for future in asyncio.as_completed(tasks):
                result = await future
                if self.is_valid_ip(result):
                    # Cancel remaining tasks
                    for task in tasks:
                        task.cancel()

                    return result

        return None

    async def get_ip_from_url(self, url):
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            ip = await loop.run_in_executor(executor, self.fetch, url)

            # Validate the IP address and return it if it's valid, otherwise return None
            return ip if self.is_valid_ip(ip) else None
