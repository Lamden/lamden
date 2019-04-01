import os
from cilantro_ee.nodes.factory import NodeFactory
from cilantro_ee.constants.conf import CilantroConf, CIL_CONF_PATH

from cilantro_ee.logger.base import overwrite_logger_level
from seneca.libs.logger import overwrite_logger_level as sen_overwrite_log


def main():

    assert os.path.exists(CIL_CONF_PATH), "No config file found at path {}. Comon man get it together!".format(CIL_CONF_PATH)

    # print("VKBook mns {}".format(VKBook.get_masternodes()))
    overwrite_logger_level(CilantroConf.LOG_LEVEL)

    if CilantroConf.NODE_TYPE == 'witness':
        NodeFactory.run_witness(signing_key=CilantroConf.SK)
        # run_witness(sk=config['sk'], log_lvl=int(config['log_lvl']), reset_db=config.getboolean('reset_db'))
    elif CilantroConf.NODE_TYPE == 'delegate':
        sen_overwrite_log(CilantroConf.SEN_LOG_LEVEL)
        NodeFactory.run_delegate(CilantroConf.SK)
        # run_delegate(sk=config['sk'], log_lvl=int(config['log_lvl']), seneca_log_lvl=int(config['seneca_log_lvl']),
        #              reset_db=config.getboolean('reset_db'))
    elif CilantroConf.NODE_TYPE == 'masternode':
        NodeFactory.run_masternode(CilantroConf.SK)
        # run_mn(sk=config['sk'], log_lvl=int(config['log_lvl']), nonce_enabled=config.getboolean('nonce_enabled'),
        #        reset_db=config.getboolean('reset_db'))

    elif CilantroConf.NODE_TYPE in ('scheduler', 'notifier'):
        while True:
            import time
            print("I am a scheduler or notifier but i has no logic yet")
            time.sleep(1)
        pass
    else:
        raise Exception("Unrecognized node type {}".format(CilantroConf.NODE_TYPE))


if __name__ == '__main__':
    main()
