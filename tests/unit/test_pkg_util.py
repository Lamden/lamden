from unittest import TestCase
from scripts.pkg import *


class TestPkgUtil(TestCase):
    def test_init_new_wallets(self):
        path = '/Volumes/dev/lamden/cilantro-enterprise/cilantro_ee'
        res = build_pepper(path)
        print(res)

