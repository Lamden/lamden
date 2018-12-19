import os, shutil
from os import getenv as env
from create_user import create_user


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
    os.system('sudo mongod --dbpath ./data/{} --logpath ./data/{}/logs/mongo.log {} &'.format(
        host_name, host_name, '' if env('CIRCLECI') == 'true' else '--bind_ip_all'
    ))

    create_user()


if __name__ == '__main__':
    # os.system("find . -name '*-ipc-sock*' -delete || true")
    from start_redis import start_redis
    from dotenv import load_dotenv
    load_dotenv()
    start_mongo()
    start_redis()
