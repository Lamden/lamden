from cilantro.networking import Witness2
from cilantro.proofs.pow import SHA3POW, POW

if __name__ == '__main__':
    w = Witness2(sub_port='8888', pub_port='8080', hasher=SHA3POW)
    w.start_async()


