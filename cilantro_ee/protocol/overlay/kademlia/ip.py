import socket, struct, requests, os, asyncio


def get_public_ip():
    async def fetch_1():
        res = (await loop.run_in_executor(None, requests.get, 'http://ip.42.pl/raw')).text
        futs.set_result(res)

    async def fetch_2():
        res = (await loop.run_in_executor(None, requests.get, 'http://jsonip.com')).json()['ip']
        futs.set_result(res)

    async def fetch_3():
        res = (await loop.run_in_executor(None, requests.get, 'http://httpbin.org/ip')).json()['origin']
        futs.set_result(res)

    async def fetch_4():
        res = (await loop.run_in_executor(None, requests.get, 'https://api.ipify.org/?format=json')).json()['ip']
        futs.set_result(res)

    try:
        tasks = fetch_1(), fetch_2(), fetch_3(), fetch_4()
        loop = asyncio.get_event_loop()
        futs = asyncio.ensure_future(asyncio.wait_for(asyncio.gather(*tasks), 3))
        return loop.run_until_complete(futs)
    except:
        raise Exception('Cannot get your public ip!')


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
