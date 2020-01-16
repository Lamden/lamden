import abc

class OverlayInterface(abc.ABC):
    def __init__(self):
        pass
        # interface dictionary

    # ready signal from client to start overlay server
    @abc.abstractmethod
    def ready(self):
        pass

    # returns ip address if found else None
    @abc.abstractmethod
    def get_ip_from_vk(self, vk):
        pass

    # returns ip address if found else None
    @abc.abstractmethod
    def get_ip_and_handshake(self, vk, is_first_time):
        pass

    @abc.abstractmethod
    def handshake_with_ip(self, vk, ip, is_first_time):
        pass

    @abc.abstractmethod
    def ping_ip(self, vk, ip, is_first_time):
        pass

