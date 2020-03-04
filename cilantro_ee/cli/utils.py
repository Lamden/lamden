import ipaddress

def validate_ip(address):
    try:
        ip = ipaddress.ip_address(address)
        print('%s is a correct IP%s address.' % (ip, ip.version))
        return True
    except ValueError:
        print('address/netmask is invalid: %s' % address)
