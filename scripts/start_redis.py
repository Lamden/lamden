import os


def start_redis():
    # if not os.getenv('CIRCLECI') and not os.getenv('VMNET_CLOUD'):
        # for package in ['seneca', 'vmnet']:
        #     os.system('cp -r ./venv/lib/python3.6/site-packages/{} /usr/local/lib/python3.6/dist-packages 2>/dev/null'.format(package))

    print("Starting Redis server...")
    redis_dir = 'redis-store/{}'.format(os.getenv('HOST_NAME', 'local'))
    redis_file = 'dump.rdb'
    os.makedirs(redis_dir, exist_ok=True)

    print("Redis using data directory: {}\nAnd db file name: {}".format(redis_dir, redis_file))
    os.system('redis-server --dir {} --dbfilename {}'.format(redis_dir, redis_file))


if __name__ == '__main__':
    start_redis()
