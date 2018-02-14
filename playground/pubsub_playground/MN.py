from cilantro.networking import Basenode, Masternode2

if __name__ == '__main__':
    mn = Masternode2(external_port='7777', internal_port='8888')
    mn.setup_web_server()