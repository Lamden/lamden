import configparser
import json
import sys
import requests
from cilantro_ee.core.crypto import wallet
import cilantro_ee

config = configparser.ConfigParser()
config['DEFAULT'] = {}

print('=======================================================================')
print('==                        Cilantro node setup                        ==')
print('==                                                                   ==')
print('== This script will setup your node for participating in the network ==')
print('=======================================================================')
print('Enter your signing key as a hex string.')
while True:
    sk = input('>>> ')
    try:
        sk = bytes.fromhex(sk)
        keys = wallet.new(seed=sk)
        break
    except:
        print('Incorrect key format.')

print('Enter name of constitution in cilantro_ee directory to use:')

while True:
    c_name = input('>>> ')
    try:
        path = cilantro_ee.__file__.split('/')[:-2]
        path = '/'.join(path)

        c_path = '{}/constitutions/public/{}'.format(path, c_name)

        print(c_path)
        const = json.load(open(c_path))
        break
    except Exception as e:
        print(e)
        print('Could not open or parse provided constitution file.')

vk = keys[1]
is_delegate = False
is_masternode = False
for d in const['delegates']:
    if d['vk'] == vk:
        is_delegate = True

for m in const['masternodes']:
    if m['vk'] == vk:
        is_masternode = True

if not is_delegate and not is_masternode:
    print('Your key is not part of the constitution. You cannot join the network!')
    sys.exit()
elif is_delegate:
    print('Your key is assigned as a delegate.\n')
    role = 'delegate'
elif is_masternode:
    print('Your key is assigned as a masternode.\n')
    role = 'masternode'

print('Fetching public IP from https://api.ipify.org...')
ip = requests.get('https://api.ipify.org').text
print('Your public IP is {}.'.format(ip))

config['DEFAULT']['ip'] = ip
config['DEFAULT']['boot_masternode_ips'] = ','.join(const['boot_masternode_ips'])
config['DEFAULT']['boot_delegate_ips'] = ','.join(const['boot_delegate_ips'])
config['DEFAULT']['node_type'] = role
config['DEFAULT']['sk'] = keys[0]
config['DEFAULT']['reset_db'] = 'True'
config['DEFAULT']['constitution_file'] = c_name
config['DEFAULT']['ssl_enabled'] = 'False'
config['DEFAULT']['log_lvl'] = '13'
config['DEFAULT']['seneca_log_lvl'] = '13'

print('Writing node config file to /etc/cilantro_ee.conf\n')

with open('/etc/cilantro_ee.conf', 'w') as c:
    config.write(c)

print('Complete! Now run bootstrap.py to join the network!')
