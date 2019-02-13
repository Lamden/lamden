from os import getenv as env


MASTER_DB = 0
DATA_DIR = '/var/db/cilantro'


def get_redis_port(port=None):
    if port is not None:
        return port

    if env('CIRCLECI'):
        return 6379

    return env('REDIS_PORT', 6379)


def get_redis_password(password=None):
    if password is not None:
        return password

    if env('CIRCLECI'):
        return ''

    return env('REDIS_PASSWORD', '')
