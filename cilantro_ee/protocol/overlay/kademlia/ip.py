import socket, struct, os, asyncio
from cilantro_ee.constants import conf


def get_public_ip():
    return conf.HOST_IP


def truncate_ip(ip):
    return ip_to_decimal('.'.join(ip.split('.')[:3] + ['0']))


def get_ip_range(ip):
    from_ip = truncate_ip(ip)
    to_ip = from_ip + 256
    return [decimal_to_ip(ip) for ip in range(from_ip, to_ip)]


def decimal_to_ip(d):
    return socket.inet_ntoa(struct.pack('!L', d))


def ip_to_decimal(ip):
    return struct.unpack("!L", socket.inet_aton(ip))[0]
