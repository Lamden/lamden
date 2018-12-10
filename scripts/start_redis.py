import os, time
from os import getenv as env

def start_redis():
    if not env('CIRCLECI'):
        for package in ['seneca', 'vmnet']:
            os.system('cp -r ./venv/lib/python3.6/site-packages/{} /usr/local/lib/python3.6/dist-packages'.format(package))

    os.system('rm -f ./dump.rdb')

    print("Starting Redis server...")

    if env('VMNET'):
        from free_port import free_port
        from random_password import random_password
        pw = random_password()
        port = free_port()
        with open('docker/redis.env', 'w+') as f:
            f.write('''
REDIS_PORT={}
REDIS_PASSWORD={}
            '''.format(port,pw))
        os.system('redis-server docker/redis.conf --port {} --requirepass {} &'.format(port,pw))
    else:
        os.system('pkill -9 redis-server')
        os.system('redis-server &')

    time.sleep(1)
    print("Done.")

if __name__ == '__main__':
    if env('VMNET'):
        from dotenv import load_dotenv
        load_dotenv()
    start_redis()
