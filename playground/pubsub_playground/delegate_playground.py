from cilantro.networking import Delegate2

if __name__ == '__main__':
    d = Delegate2(sub_port='8080', pub_port='7799')
    d.start_async()




