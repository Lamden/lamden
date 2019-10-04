# def wrap_func(fn, *args, **kwargs):
#     def wrapper():
#         return fn(*args, **kwargs)
#     return wrapper
#
#
# def log_create(name, vk, ip):
#     from cilantro_ee.core.logger import get_logger
#     log = get_logger("{}Builder".format(name))
#     delim = '=' * 64
#     msg = '\n' + delim + '\n' + 'Creating {} with:\nvk={}\nip={}\n'.format(name, vk, ip) + delim
#     log.test(msg)
#
#
# def run_mn(slot_num=None, sk=None, log_lvl=11, reset_db=False, nonce_enabled=True):
#     assert slot_num is not None or sk is not None, "SK or slot num must be provided"
#
#     # Due to some Sanic BS, we cannot set the log level between [1,10]
#     assert log_lvl not in range(2, 11), "Due to a Sanic logging bug, Masternode cant set log lvl in the range (1,10]"
#
#     from cilantro_ee.constants.conf import CilantroConf
#     from cilantro_ee.core.logger import get_logger, overwrite_logger_level
#     from cilantro_ee.nodes.factory import NodeFactory
#     from cilantro_ee.utils.test.node_runner import log_create
#     from cilantro_ee.core.crypto import wallet
#
#     overwrite_logger_level(log_lvl)
#     vk = wallet.get_vk(sk)
#
#     ip = CilantroConf.HOST_IP
#     log_create("Masternode", vk, ip)
#     NodeFactory.run_masternode(ip=ip, signing_key=sk, reset_db=reset_db)
#
#
# def run_witness(slot_num=None, sk=None, log_lvl=11, reset_db=False):
#     assert slot_num is not None or sk is not None, "SK or slot num must be provided"
#     from cilantro_ee.core.logger import get_logger, overwrite_logger_level
#     from cilantro_ee.nodes.factory import NodeFactory
#     from cilantro_ee.constants.testnet import TESTNET_WITNESSES
#     from cilantro_ee.constants.conf import CilantroConf
#     from cilantro_ee.utils.test.node_runner import log_create
#     from cilantro_ee.core.crypto import wallet
#
#     overwrite_logger_level(log_lvl)
#
#     vk = wallet.get_vk(sk)
#
#     ip = CilantroConf.HOST_IP
#     log_create("Witness", vk, ip)
#     NodeFactory.run_witness(ip=ip, signing_key=sk, reset_db=reset_db)
#
#
# def run_delegate(slot_num=None, sk=None, log_lvl=11, seneca_log_lvl=11, bad_actor=False, reset_db=False, bad_sb_set={1}, num_succ_sbs=3):
#     assert slot_num is not None or sk is not None, "SK or slot num must be provided"
#     from cilantro_ee.constants.conf import CilantroConf
#     import os
#     if bad_actor:
#         os.environ["BAD_ACTOR"] = '1'
#         os.environ["SB_IDX_FAIL"] = ','.join((str(i) for i in bad_sb_set))
#         os.environ["NUM_SUCC_SBS"] = str(num_succ_sbs)
#
#     from cilantro_ee.core.logger import get_logger, overwrite_logger_level
#     from eneca.libs.logger import overwrite_logger_level as sen_overwrite_log
#     from cilantro_ee.nodes.factory import NodeFactory
#     from cilantro_ee.utils.test.node_runner import log_create
#     from cilantro_ee.core.crypto import wallet
#
#     overwrite_logger_level(log_lvl)
#     sen_overwrite_log(seneca_log_lvl)
#
#     vk = wallet.get_vk(sk)
#
#     ip = CilantroConf.HOST_IP
#     log_create("Delegate", vk, ip)
#     NodeFactory.run_delegate(ip=ip, signing_key=sk, reset_db=reset_db)
#
#
# def dump_it(volume, delay=0):
#     from cilantro_ee.utils.test.god import God
#     from cilantro_ee.core.logger import get_logger, overwrite_logger_level
#     import logging
#
#     overwrite_logger_level(logging.WARNING)
#     God.dump_it(volume=volume, delay=delay)
#
#
# def pump_it(*args, **kwargs):
#     from cilantro_ee.utils.test.god import God
#     from cilantro_ee.core.logger import get_logger, overwrite_logger_level
#     import logging, time
#
#     overwrite_logger_level(logging.WARNING)
#
#     log = get_logger("Pumper")
#     log.important("Starting the pump..")
#     God.pump_it(*args, **kwargs)
