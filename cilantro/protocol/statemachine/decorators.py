def input(msg_type):
    def decorate(func):
        func._recv = msg_type
        return func
    return decorate


def input_request(msg_type):
    def decorate(func):
        func._reply = msg_type
        return func
    return decorate


def timeout(msg_type):
    def decorate(func):
        func._timeout = msg_type
        return func
    return decorate