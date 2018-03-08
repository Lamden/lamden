from cilantro.networking import Masternode

if __name__ == '__main__':
    mn = Masternode(external_port='7777', internal_port='8888')
    mn.setup_web_server()