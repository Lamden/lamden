from cilantro.networking import Witness2
from cilantro.protocol.proofs import SHA3POW

if __name__ == '__main__':
    w = Witness2(sub_port='8888', pub_port='8080', hasher=SHA3POW)
    w.start_async()


