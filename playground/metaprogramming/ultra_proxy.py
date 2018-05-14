"""
Proxy complex commands to subprocesses or processes running on VM's, or even literally physically different machines
"""

class CommandContext:
    def __init__(self, name, obj, is_root=False):
        self.is_root = is_root
        self.name = name
        self.obj = obj
        self.args, self.kwargs, self.child = None, None, None

        print("proxy master created with name {}".format(name))

    def __getattr__(self, item):
        # if self.is_root:
        #     return CommandContext(name=self.name, obj=self.object)
        assert hasattr(self.obj, item), "Object {} has no attribute/func {}".format(self.obj, item)

        print("__getattr__ on {} with item {}".format(self.name, item))
        print("type of item: {}".format(type(item)))

        child_ctx = CommandContext(name=str(item), obj=getattr(self.obj, item))
        child_ctx.parent = self
        self.child = child_ctx

        return child_ctx

    def __call__(self, *args, **kwargs):
        print("(__call__) {} got called with args {} and kwargs {}".format(self.name, args, kwargs))

        self.args = args
        self.kwargs = kwargs

        self.obj = self.obj(*args, **kwargs)

        return self

    def __repr__(self):
        if self.args and self.kwargs:
            return ".{}(args={}, kwargs={})".format(self.name, self.args, self.kwargs)
        else:
            return ".{}".format(self.name)


def print_cmd_tree(node: CommandContext, obj):
    if node.is_root:
        print("node {} is root!. skipping and calling child")
        return print_cmd_tree(node.child, obj)

    if node.args is not None:
        assert node.args is not None and node.kwargs is not None, "Both args and kwargs should be set, or neither at all"
        print("get attribute {} and call it with args {} and kwargs {}".format(node.name, node.args, node.kwargs))
        assert hasattr(obj, node.name), "Object {} does not have attr named {}".format(obj, node.name)
        assert callable(getattr(obj, node.name)), "Object {} /w attribute {} is not callable but was invoked /w args"\
                                                     .format(obj, node.name)
        obj = getattr(obj, node.name)(*node.args, **node.kwargs)
    else:
        assert node.args is None and node.kwargs is None, "if args is not set, then kwargs should not be either"
        print("attribute {} accessed (property read, not func call)".format(node.name))
        assert hasattr(obj, node.name), "Object {} does not have attr named {}".format(obj, node.name)

        obj = getattr(obj, node.name)

    if not node.child:
        print("done traversing commands at node {}".format(node))
        return
    else:
        return print_cmd_tree(node.child, obj)


class Car:
    def __init__(self):
        self.cockpit = CockPit()

class CockPit:
    def __init__(self):
        self.pilot = Pilot()


class Pilot:
    def turn(self, direction: str, speed=10):
        print("\n\n\TURNING {} at speed {}\n\n".format(direction, speed))

    def honk(self, num_times=1, msg=""):
        print("\n\nHONKING with msg {}\n\n".format(msg))
        if num_times > 1:
            return self.honk(num_times-1, msg)


if __name__ == '__main__':
    # obj = CommandContext("BaseObject")

    # print("about to access some shit")

    # command = obj.prop1.prop2('did this get passed in a sure hope so').do_this("another one!",
    #                                                                            arg1=b'ass', thicc_prime=pow(2, 31) - 1)


    car = Car()

    cmd = CommandContext(name="car", is_root=True, obj=car)
    cmd.cockpit.pilot.turn(direction="left", speed=100)

    cmd2 = CommandContext("car", is_root=True, obj=car)
    cmd2.cockpit.pilot.honk(3, "fuck u guy")

    # print("----------------- command tree for turning-----------------")
    # print_cmd_tree(cmd, car)
    #
    # print("----------------- command tree for honking -----------------")
    # print_cmd_tree(cmd2, car)



