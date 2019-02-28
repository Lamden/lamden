# TODO this is too fragile... use API in testnet_config.py instead
# NOTE -- globals() loads the global namespace where the calling function is DEFINED, not necessarily where it
# is actually called. Thus we need to do this sorcery to inject stuff into the namespace where people call
# patch_testnet_json_file, not into the namespace of this file where patch_testnet_json_file is defined
def patch_testnet_json_file(file_name):
    return """
from unittest.mock import patch
with patch('cilantro_ee.utils.test.testnet_nodes.DEFAULT_TESTNET_FILE_NAME', '{file_name}'):
    import cilantro_ee.constants.testnet as testnet_constants
    for obj_name in dir(testnet_constants):
        if obj_name[0] != '_' and obj_name.isupper():
            print("Injecting variable named " + obj_name)  # TODO remove
            globals()[obj_name] = getattr(testnet_constants, obj_name)
""".format(file_name=file_name)
