import abc

class OverlayInterface(abc.ABC):
    def __init__(self):
        pass
        # interface dictionary

    # returns ip address if found else None
    @abc.abstractmethod
    def get_ip_from_vk(self, vk):
        pass

    # returns ip address if found else None
    @abc.abstractmethod
    def get_ip_and_handshake(self, vk, is_first_time):
        pass

    @abc.abstractmethod
    def handshake_with_ip(self, ip):
        pass

    @abc.abstractmethod
    def ping_ip(self, ip, is_first_time):
        pass

    # don't need this probably
    @abc.abstractmethod
    def add_event_handler(self):
        pass

