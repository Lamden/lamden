

class CommandProxyTest:

    def __getattr__(self, attr_name):
        print("CALLED GET ATTR WITH NAME: {}".format(attr_name))



cpt = CommandProxyTest()

cpt.hi
