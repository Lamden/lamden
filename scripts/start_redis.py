import os


def start_redis():
    redis_dir = '/var/db/cilantro'
    print("Starting Redis server...")

    if not os.path.exists(redis_dir):
        print("Creating Redis directory at {}".format(redis_dir))
        os.makedirs(redis_dir, exist_ok=True)

    redis_file = 'dump.rdb'

    print("Redis using data directory: {}\nAnd db file name: {}".format(redis_dir, redis_file))
    os.system('redis-server --dir {} --dbfilename {}'.format(redis_dir, redis_file))


if __name__ == '__main__':
    start_redis()
