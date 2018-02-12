from cilantro.networking import PubSubBase
import json

if __name__ == '__main__':
    pub = PubSubBase(sub_port='5555', pub_port='7777')
    pub.publish_req({'fake-key': 'fake-value'})
    # print("a")