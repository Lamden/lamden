import subprocess


def start_rocks():
    subprocess.Popen(['rocks', 'serve'], stdout=open('/dev/null', 'w'), stderr=open('/dev/null', 'w'))


def start_mongo():
    pass
