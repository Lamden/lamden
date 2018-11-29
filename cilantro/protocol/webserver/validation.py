from cilantro.storage.vkbook import VKBook
import re

def _is_valid_name(name_type, name):
    assert re.match(r'^[\w]{6,64}$', name), '{} must be 6 - 64 alphanumeric characters'.format(name_type)

def validate_contract_name(name):
    _is_valid_name('Contract name', name)
    return name

def validate_author(name):
    _is_valid_name('Author', name)
    return name
