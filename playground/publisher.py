from cilantro.networking import BaseNode, Masternode2
from cilantro.serialization import JSONSerializer
from cilantro.networking import Masternode
import asyncio
import json

if __name__ == '__main__':
    pub = BaseNode(host='127.0.0.1', sub_port='5555', pub_port='7777', serializer=JSONSerializer)
    pub.publish_req({'fake-key': 'fake-value'})
    # print("a")

    # loop = asyncio.get_event_loop()
    # loop.run_until_complete()
