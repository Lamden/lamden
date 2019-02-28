from cilantro_ee.storage.vkbook import VKBook
from seneca.libs.datatypes import DATATYPES
import re

def _is_valid_name(name_type, name):
    assert re.match(r'^[\w]{3,64}$', name), '{} must be 3 to 64 alphanumeric characters'.format(name_type)

def validate_contract_name(name):
    _is_valid_name('Contract name', name)
    return name

def validate_contract_call(name):
    assert re.match(r'^[\w]{3,64}\.[\w]{1,64}$', name), 'Invalid contract call parameter'
    return name

def validate_author(name):
    _is_valid_name('Author', name)
    return name

def validate_key_name(name):
    _is_valid_name('Key', name)
    return name
