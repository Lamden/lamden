from datetime import datetime
from dateutil import parser
import asyncio
import json
import os
import re
import socketio
import subprocess

sio = socketio.AsyncClient(logger=True, engineio_logger=True)

def validate_ip_address(ip_str):
    pattern = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
    match = re.search(pattern, ip_str)

    return True if match else False

def parse_bootnodes(ips: list):
    return ':'.join(list(filter(lambda ip: validate_ip_address(ip), ips)))

@sio.event
async def connect():
    print('Connected to event service!')
    await sio.emit('join', {'room': 'upgrade'})

@sio.event
async def disconnect():
    print('Disconnected from event service!')
    await sio.emit('leave', {'room': 'upgrade'})

@sio.event
async def event(data):
    data = json.loads(data['data'])
    print(f'Received data: {data}')

    os.environ['LAMDEN_TAG'] = data['lamden_tag']
    os.environ['CONTRACTING_TAG'] = data['contracting_tag']
    os.environ['BOOTNODES'] = parse_bootnodes(data['bootnode_ips'])
    utc_when = parser.parse(data['utc_when'])

    subprocess.check_call(['make', 'build'])

    while utc_when < datetime.utcnow():
        asyncio.sleep(0.1)

    subprocess.check_call(['make', 'restart'])

async def main():
    await sio.connect(f'http://localhost:{os.environ["LAMDEN_ES_PORT"]}')
    await sio.wait()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
