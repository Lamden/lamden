# TODO
# implement this class for realz ... My idea was to have this class spin up a subproc and
# talk to the overlay process over an dealer/router socket over IPC. Perhaps this isnt the best solution tho
# I shall defer to good sir falcon on how to best talk with the overlay  --davis


ip_vk_map = {
    '82540bb5a9c84162214c5540d6e43be49bbfe19cf49685660cab608998a65144': '172.29.5.0',  # Masternode 1
    '0e669c219a29f54c8ba4293a5a3df4371f5694b761a0a50a26bf5b50d5a76974': '172.29.5.1',  # Witness 1
    '50869c7ee2536d65c0e4ef058b50682cac4ba8a5aff36718beac517805e9c2c0': '172.29.5.2',  # Witness 2
    '3dd5291906dca320ab4032683d97f5aa285b6491e59bba25c958fc4b0de2efc8': '172.29.5.3',  # Delegate 1 (aka delegate_3)
    'ab59a17868980051cc846804e49c154829511380c119926549595bf4b48e2f85': '172.29.5.4',  # Delegate 2 (aka delegate_4)
    '0c998fa1b2675d76372897a7d9b18d4c1fbe285dc0cc795a50e4aad613709baf': '172.29.5.5',  # Delegate 3 (aka delegate_5)
}

# TODO delete this
nodemap = {'masternode': '172.29.5.0', 'witness_1': '172.29.5.1', 'witness_2': '172.29.5.2',
 'delegate_3': '172.29.5.3', 'delegate_4': '172.29.5.4', 'delegate_5': '172.29.5.5',
 'mgmt': '172.29.5.6'}

class OverlayInterface:
    """
    This class provides a high level API to interface with the overlay network
    """

    @classmethod
    def ip_for_vk(cls, vk: str):
        # this entire func is obviously a horrendous hack but until we properly integrate the overlay it must be done
        assert vk in ip_vk_map, "Got VK {} that is not in ip_vk_map keys {}".format(vk, ip_vk_map.keys())
        return ip_vk_map[vk]
