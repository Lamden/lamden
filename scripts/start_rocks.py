import os, sys

def start_rocks():
    print("Starting Rocks server...")
    os.system('export LC_ALL=C.UTF-8; export LANG=C.UTF-8; rocks serve')

if __name__ == '__main__':
    start_rocks()

