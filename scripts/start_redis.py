import os, time
from os import getenv as env
from free_port import free_port
from random_password import random_password

def start_redis():
    if not env('CIRCLECI') and not env('VMNET_CLOUD'):
        for package in ['seneca', 'vmnet']:
            os.system('cp -r ./venv/lib/python3.6/site-packages/{} /usr/local/lib/python3.6/dist-packages 2>/dev/null'.format(package))

    print("Starting Redis server...")
    redis_dir = 'redis-store/{}'.format(os.getenv('HOST_NAME', 'local'))
    redis_file = 'dump.rdb'
    os.makedirs(redis_dir, exist_ok=True)
    os.system('sudo pkill -9 redis-server')

    if env('CIRCLECI'):
        os.system('redis-server')
    elif not env('VMNET_CLOUD'):
        os.system('redis-server --dir {} --dbfilename {} &'.format(redis_dir, redis_file))

    pw = random_password()
    port = free_port()
    with open('docker/redis.env', 'w+') as f:
        f.write('''
REDIS_PORT={}
REDIS_PASSWORD={}
        '''.format(port,pw))

    if env('VMNET_CLOUD') or not env('VMNET_DOCKER'):
        run_async = '&'
    else:
        run_async = ''
    os.system('redis-server docker/redis.conf --dir {} --dbfilename {} --port {} --requirepass {} {}'.format(redis_dir, redis_file, port, pw, run_async))

if __name__ == '__main__':
    # os.system("find . -name '*-ipc-sock*' -delete || true")
    from dotenv import load_dotenv
    load_dotenv()
    start_redis()
