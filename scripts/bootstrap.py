from cilantro_ee.nodes.factory import NodeFactory
from cilantro_ee.constants.conf import CilantroConf, CIL_CONF_PATH

from cilantro_ee.logger.base import overwrite_logger_level
from contracting.logger import overwrite_logger_level as sen_overwrite_log
import os, sys, time


def boot(delay):
    assert os.path.exists(CIL_CONF_PATH), "No config file found at path {}. Comon man get it together!".format(CIL_CONF_PATH)

    print("Bootstrapping node with start delay of {}...".format(delay))
    time.sleep(delay)

    # print("VKBook mns {}".format(VKBook.get_masternodes()))
    overwrite_logger_level(CilantroConf.LOG_LEVEL)

    if CilantroConf.NODE_TYPE == 'witness':
        NodeFactory.run_witness(signing_key=CilantroConf.SK)

    elif CilantroConf.NODE_TYPE == 'delegate':
        sen_overwrite_log(CilantroConf.SEN_LOG_LEVEL)
        NodeFactory.run_delegate(CilantroConf.SK)

    elif CilantroConf.NODE_TYPE == 'masternode':
        NodeFactory.run_masternode(CilantroConf.SK)

    elif CilantroConf.NODE_TYPE == 'scheduler':
        NodeFactory.run_scheduler(CilantroConf.SK)

    elif CilantroConf.NODE_TYPE == 'notifier':
        while True:
            print("I am a notifier but i has no logic yet :(")
            time.sleep(1)
        pass

    else:
        raise Exception("Unrecognized node type {}".format(CilantroConf.NODE_TYPE))


if __name__ == '__main__':
    _delay = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    boot(_delay)
