from cilantro.networking import BaseNode, Masternode2
from cilantro.serialization import JSONSerializer
from cilantro.networking import Masternode
import asyncio
import json

if __name__ == '__main__':
    try:
        JSONSerializer.serialize()
    except Exception as e:
        print(e)


