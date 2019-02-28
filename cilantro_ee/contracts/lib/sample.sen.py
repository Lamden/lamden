@export
def reasonable_call():
    print('Hello there')

@export
def do_that_thing():
    return 'sender: {}, author: {}'.format(rt.sender, rt.author)

@export
def test_global_namespace():
    print('sender: {}, author: {}'.format(rt.sender, rt.author))
    print("sbb_idx: {}".format(sbb_idx))
    print("ALL GLOBALS: {}".format(globals()))

def secret_call():
    return False
