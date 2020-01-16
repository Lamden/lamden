from cilantro_ee.core.logger import get_logger
from deprecated.test import God
import os, glob
import asyncio, aiohttp


SSL_ENABLED = False  # TODO make this infered instead of a hard coded flag

IP_FILE_PREFIX = 'ip_masternode'


class Dumpatron:

    TX_PER_BLOCK = 0
    STAMPS_AMOUNT = 0

    def __init__(self, env_path):
        if env_path[-1] != '/':
            env_path += '/'
        assert os.path.exists(env_path), "No env dir found at path {}".format(env_path)
        assert os.path.exists(env_path + '.cache'), "No .cache dir found at path {}.cache".format(env_path)
        self.log = get_logger("Dumpatron")
        Dumpatron.TX_PER_BLOCK = TRANSACTIONS_PER_SUB_BLOCK * NUM_SB_PER_BLOCK * NUM_BLOCKS

        self.env_path = env_path
        self.mn_ip_dict = self._extract_mn_ips()
        self.mn_url_list = self._get_mn_urls_from_ips(self.mn_ip_dict)

        God.mn_urls = self.mn_url_list
        God.multi_master = True

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.session = aiohttp.ClientSession()

        God.wait_for_mns_online()

    async def _start(self):
        await self.start_interactive_dump()

    async def _start_loop(self):
        try:
            await self._start()
        except asyncio.CancelledError:
            self.log.warning("Loop cancelled")
        finally:
            await self.session.close()

    def start(self):
        self.loop.run_until_complete(self._start_loop())

    def _extract_mn_ips(self) -> dict:
        ips = {}
        pattern = "{}.cache/{}*".format(self.env_path, IP_FILE_PREFIX)
        mn_files = glob.glob(pattern)
        assert len(mn_files) > 0, "No masternode ip config files found matching glob pattern {} (Did you do make run " \
                                  "first? Otherwise, harass Colin...did he change the" \
                                  " way IPs are cached?)".format(pattern)

        for mn_file in mn_files:
            with open(mn_file, 'r') as f:
                mn_idx = mn_file[len(IP_FILE_PREFIX):]
                ips[mn_file[-1]] = f.read()
        return ips

    # TODO factor this out into its own function/module so it can be used in God as well
    def _get_mn_urls_from_ips(self, ips: dict) -> list:
        urls = []
        for ip in ips.values():
            if SSL_ENABLED:
                urls.append("https://{}".format(ip))
            else:
                urls.append("http://{}:8080".format(ip))
        return urls

    async def start_interactive_dump(self):
        self.log.info("Starting the dump....")
        while True:
            user_input = input("Enter an integer representing the # of transactions to dump, or 'x' to quit. "
                               "Press enter to dump 1 blocks\n")

            if user_input.lower() == 'x':
                self.log.important("Termination input detected. Breaking")
                break

            vol = int(user_input) if user_input.isdigit() else self.TX_PER_BLOCK
            self.log.important3("Dumping {} transactions!".format(vol))
            await God.dump_it(self.session, volume=vol)

    def _parse_reply(self, req, req_type='json'):
        if req.status_code != 200:
            self.log.spam("Got status code {} from request {}".format(req.status_code, req))
            return None

        if req_type == 'json':
            return req.json()
        else:
            raise Exception("Unknown request type {}".format(req_type))



