from cilantro_ee.crypto.wallet import Wallet

import random


def make_ip():
    return '.'.join([str(random.randint(0, 255)) for _ in range(4)])


def make_random_constitution(mns=2, dls=2):
    masternodes = {Wallet().verifying_key: make_ip() for _ in range(mns)}
    delegates = {Wallet().verifying_key: make_ip() for _ in range(dls)}

    return {
        'masternodes': masternodes,
        'delegates': delegates
    }


raw_constitution = {
    'masternodes': {
        'vk': 'ip'
    },
    'delegates': {
        'vk': 'ip'
    }
}