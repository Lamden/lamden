import socket, struct, requests, os, asyncio

def get_public_ip():
    async def fetch_1():
        return (await loop.run_in_executor(None, requests.get, 'http://ip.42.pl/raw')).text
    async def fetch_2():
        return (await loop.run_in_executor(None, requests.get, 'http://jsonip.com')).json()['ip']
    async def fetch_3():
        return (await loop.run_in_executor(None, requests.get, 'http://httpbin.org/ip')).json()['origin']
    async def fetch_4():
        return (await loop.run_in_executor(None, requests.get, 'https://api.ipify.org/?format=json')).json()['ip']
    try:
        tasks = fetch_1(), fetch_2(), fetch_3(), fetch_4()
        loop = asyncio.get_event_loop()
        ips = loop.run_until_complete(asyncio.gather(*tasks))
        assert len(set(ips)) > 0, 'Not connected to internet'
        return ips[0]
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
