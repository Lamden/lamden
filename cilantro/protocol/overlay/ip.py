import socket, struct
import requests
import csv
import os

path = os.path.dirname(__file__)
WORLD_IP_FILE = '{}/data/world.csv'.format(path)
NEIGHBOR_IP_FILE = '{}/data/neighborhood.txt'.format(path)
POPULAR_IP_FILE = '{}/data/popular.txt'.format(path)

def get_public_ip():
    return '127.0.0.1'
    try:
        r = requests.get('http://ip.42.pl/raw')
        return r.text
    except:
        raise Exception('Cannot get your public ip!')

def get_subnet(ip):
    return '.'.join(ip.split('.')[:-1])

def truncate_ip(ip):
    return ip_to_decimal('.'.join(ip.split('.')[:3]+['0']))

def get_local_range(ip):
    from_ip = truncate_ip(ip)
    to_ip = from_ip + 256
    return from_ip, to_ip

def get_subnets_range(ip):
    from_ip = ip_to_decimal('.'.join(ip.split('.')[:2]+['0.0']))
    to_ip = from_ip + 256 * 256
    return from_ip, to_ip

def decimal_to_ip(d):
    return socket.inet_ntoa(struct.pack('!L', d))

def ip_to_decimal(ip):
    return struct.unpack("!L", socket.inet_aton(ip))[0]

def get_region_range(ip, max_away=5, recalculate=False):
    data = []
    if not os.path.exists(NEIGHBOR_IP_FILE) or recalculate:
        print('Calculating neighboring ip ranges...')
        ip_idx = 0
        idx_set = False
        ip_decimal = ip_to_decimal(ip)
        with open(WORLD_IP_FILE) as f:
            lines = csv.DictReader(f, delimiter=',', quotechar='"')
            for row in lines:
                if ip_decimal < int(row['from_ip']) and not idx_set:
                    idx_set = True
                elif not idx_set:
                    ip_idx += 1
                data.append('{},{}'.format(decimal_to_ip(int(row['from_ip'])), row['city']))

        with open(NEIGHBOR_IP_FILE, 'w+') as f:
            data = data[ip_idx-max_away:ip_idx+max_away]
            data.append('{},{}'.format(os.getenv('HOST_IP', '127.0.0.1'), 'virtual_network'))
            for d in data:
                f.write("{}\n".format(d))
        print('Saved to {}!'.format(NEIGHBOR_IP_FILE))
    else:
        with open(NEIGHBOR_IP_FILE) as f:
            for line in f:
                data.append(line.strip())
    print('Loaded neighboring {} ip ranges!'.format(len(data)))
    return data
