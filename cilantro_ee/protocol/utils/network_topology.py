from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.constants.system_config import NUM_SB_BUILDERS, NUM_SB_PER_BUILDER
from cilantro_ee.constants.ports import *


class NetworkTopology:

    @classmethod
    def get_sbb_publishers(cls, delegate_vk: str, sbb_idx: int) -> list:
        """ Returns a list of dicts of info that a sub-block builder should be subscribing to
        :param delegate_vk: the VK of the delegate
        :param sbb_idx: the index of the sub-block builder
        :return: A list of dicts with keys 'sb_idx', 'vk', and 'port' """
        assert delegate_vk in PhoneBook.delegates, "vk {} not in delegate vk book {}".format(delegate_vk, PhoneBook.delegates)

        port = MN_TX_PUB_PORT
        pubs = []
        for i in range(NUM_SB_PER_BUILDER):
            sb_idx = i * NUM_SB_BUILDERS + sbb_idx
            # mn_vk = VKBook.get_masternodes()[sb_idx % len(VKBook.get_masternodes())]
            # sb_idx will be less than # of masternodes
            mn_vk = PhoneBook.masternodes[sb_idx]
            pubs.append({'sb_idx': sb_idx, 'port': port, 'vk': mn_vk})

        return pubs

    @classmethod
    def get_sbb_publisher(cls, master_vk: str):
        """ Returns a list of dicts of info that a sub-block builder should be subscribing to
        :param master_vk: the VK of the master to look up for
        :return: A list of dicts with keys 'sb_idx', 'vk', and 'port' """
        # assert master_vk in VKBook.get_masternodes(), "vk {} not in master vk book {}".format(master_vk, VKBook.get_masternodes())

        if master_vk not in PhoneBook.masternodes:
            return None
        port = MN_TX_PUB_PORT
        for i, vk in enumerate(PhoneBook.masternodes, 0):
            if vk == master_vk:
                return {'sb_idx': i, 'port': port, 'vk': vk}

        return None      # this should be never reached
