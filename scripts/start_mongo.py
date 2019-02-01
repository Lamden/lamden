import os, shutil
from os import getenv as env


# TODO make this less jank
def start_mongo():
    if env('VMNET_CLOUD'):
        host_name = ''
        if env('ANNIHILATE'):
            shutil.rmtree('./data', ignore_errors=True)
    else:
        host_name = env('HOST_NAME', '')

    print("Waiting for mongo on localhost")
    try:
        os.makedirs('./data/{}/logs'.format(host_name), exist_ok=True)
        with open('./data/{}/logs/mongo.log'.format(host_name), 'w+') as f:
            print('Dir created')
    except:
        pass

    print('Starting mongo server...')
    os.system('sudo pkill -9 mongod')
    os.system('mongod --dbpath ./data/{} --logpath ./data/{}/logs/mongo.log {}'.format(
        host_name, host_name, '' if env('CIRCLECI') == 'true' else '--bind_ip_all'
    ))

    # create_user()


if __name__ == '__main__':
    start_mongo()
