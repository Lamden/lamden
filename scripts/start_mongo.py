import os, shutil
from os import getenv as env


# TODO make this more clear (or just a shell file...?)
def start_mongo():
    host_name = env('HOST_NAME', '')

    # Why is below necessary?
    try:
        os.makedirs('./data/{}/logs'.format(host_name), exist_ok=True)
        with open('./data/{}/logs/mongo.log'.format(host_name), 'w+') as f:
            print('Dir created')
    except:
        pass

    print("current file {}".format(__file__))

    print('Starting Mongo server...')
    os.system('mongod --dbpath ./data/{} --logpath ./data/{}/logs/mongo.log {}'.format(
        host_name, host_name, '' if env('CIRCLECI') == 'true' else '--bind_ip_all'
    ))


if __name__ == '__main__':
    start_mongo()
