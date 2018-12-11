import os
from os import getenv as env

def start_mongo():

    if env('VMNET'):
        host_name = ''
    else:
        host_name = env('HOST_NAME', '')

    print("Waiting for mongo on localhost")
    os.makedirs('./data/{}/logs'.format(host_name), exist_ok=True)
    with open('./data/{}/logs/mongo.log'.format(host_name), 'w+') as f:
        print('Dir created')

    import create_user

    os.system('mongod --dbpath ./data/{} --logpath ./data/{}/logs/mongo.log {} &'.format(
        host_name, host_name, '' if env('CIRCLECI') == 'true' else '--bind_ip_all'
    ))

if __name__ == '__main__':
    from start_redis import start_redis
    from dotenv import load_dotenv
    load_dotenv()
    start_mongo()
    start_redis()
