from multiprocessing import Process, Pipe
from time import sleep


def subscribe(pipe):
    while True:
        if pipe.poll():
            msg = pipe.recv()
            if msg == b'z':
                print('sleeping one second zzz...')
                sleep(1)
            elif msg == b'p':
                print(msg)
        else:
            pass


parent_pipe, child_pipe = Pipe()
listener = Process(target=subscribe, args=(child_pipe, ))
listener.start()

parent_pipe.send(b'z')
parent_pipe.send(b'p')
parent_pipe.send(b'p')
parent_pipe.send(b'p')

sleep(1.2)

listener.terminate()