from cilantro.networking import PubSubBase, Masternode2
from cilantro.serialization import JSONSerializer
from cilantro.networking import Masternode
import asyncio
import json

if __name__ == '__main__':
    mn = Masternode2(external_port=7777, internal_port=8888)
    mn.setup_web_server()