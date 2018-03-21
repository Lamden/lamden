from cilantro.networking import BaseNode
from cilantro.serialization import JSONSerializer


def beat():
    return b'hh'


class Defib(BaseNode):
    def __init__(self, host='127.0.0.1', sub_port='4242', serializer=JSONSerializer, pub_port='8888'):
        BaseNode.__init__(self, host=host, sub_port=sub_port, pub_port=pub_port, serializer=serializer)
        self.publish_req(beat())

    def publish_req(self, data):
        """
        Function to publish data to pub_socket (pub_socket is connected during initialization)
        TODO -- add support for publishing with filters

        :param data: A python dictionary signifying the data to publish
        :return: A dictionary indicating the status of the publish attempt
        """
        try:
            self.pub_socket.send(data)
        except Exception as e:
            print("error publishing request: {}".format(e))
            return {'status': 'Could not publish request'}

        print("Successfully published request: {}".format(data))
        return {'status': 'Successfully published request: {}'.format(data)}

h = Defib()
# h.start_async()
