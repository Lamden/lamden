import json


class SocketEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, SocketStruct):
            return str(o)
        return json.JSONEncoder.default(self, o)


class Protocols:
    TCP = 0
    INPROC = 1
    IPC = 2
    PROTOCOL_STRINGS = ['tcp://', 'inproc://', 'ipc://']


def _socket(s: str):
    return SocketStruct.from_string(s)


class SocketStruct:
    def __init__(self, protocol: int, id: str, port: int=0):
        self.protocol = protocol
        self.id = id

        if protocol == Protocols.INPROC:
            port = 0
        self.port = port

    def zmq_url(self):
        if not self.port:
            return '{}{}'.format(Protocols.PROTOCOL_STRINGS[self.protocol], self.id)
        else:
            return '{}{}:{}'.format(Protocols.PROTOCOL_STRINGS[self.protocol], self.id, self.port)

    # @classmethod
    # def from_string(cls, str):
    #     protocol = Protocols.TCP
    #
    #     for protocol_string in Protocols.PROTOCOL_STRINGS:
    #         if len(str.split(protocol_string)) > 1:
    #             protocol = Protocols.PROTOCOL_STRINGS.index(protocol_string)
    #             str = str.split(protocol_string)[1]
    #
    #     if protocol not in {Protocols.INPROC, Protocols.IPC}:
    #         _id, port = str.split(':')
    #         port = int(port)
    #
    #         return cls(protocol=protocol, id=_id, port=port)
    #     else:
    #         return cls(protocol=protocol, id=str, port=None)

    @classmethod
    def from_string(cls, _str: str):
        protocol = 0
        p_str = Protocols.PROTOCOL_STRINGS[0]
        for i in range(len(Protocols.PROTOCOL_STRINGS)):
            p = Protocols.PROTOCOL_STRINGS[i]
            if _str.startswith(p):
                protocol = i
                p_str = p

        end = _str.split(p_str)[1]

        if protocol == Protocols.TCP:
            _id, port = end.split(':')
            port = int(port)

            return cls(protocol=protocol, id=_id, port=port)
        else:
            return cls(protocol=protocol, id=end, port=None)

    @classmethod
    def is_valid(cls, s):
        return ':' in s

    def __str__(self):
        return self.zmq_url()

    def __repr__(self):
        return '<ZMQ Socket: "{}">'.format(self.__str__())

    def __eq__(self, other):
        return self.protocol == other.protocol and \
            self.id == other.id and \
            self.port == other.port


def resolve_tcp_or_ipc_base(base_string: str, tcp_port, ipc_dir, bind=False):
    if base_string.startswith('tcp://'):
        if bind:
            return SocketStruct.from_string(f'tcp://*:{tcp_port}')
        return SocketStruct.from_string(f'{base_string}:{tcp_port}')
    elif base_string.startswith('ipc://'):
        return SocketStruct.from_string(f'{base_string}/{ipc_dir}')


def strip_service(socket_str):
    if socket_str.startswith('tcp://'):
        sock_str = socket_str.lstrip('tcp://').split(':')[0]
        return 'tcp://' + sock_str
    elif socket_str.startswith('ipc://'):
        return '/'.join(socket_str.split('/')[:-1])
    else:
        return socket_str