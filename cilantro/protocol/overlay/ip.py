import socket, struct, requests, os

def get_public_ip():
    try:
        r = requests.get('http://ip.42.pl/raw')
        return r.text
    except:
        raise Exception('Cannot get your public ip!')

def truncate_ip(ip):
    return ip_to_decimal('.'.join(ip.split('.')[:3]+['0']))

def get_ip_range(ip):
    from_ip = truncate_ip(ip)
    to_ip = from_ip + 256
    return [decimal_to_ip(ip) for ip in range(from_ip, to_ip)]

def decimal_to_ip(d):
    return socket.inet_ntoa(struct.pack('!L', d))

def ip_to_decimal(ip):
    return struct.unpack("!L", socket.inet_aton(ip))[0]
