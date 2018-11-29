from cilantro.storage.vkbook import VKBook
import re

def _is_valid_name(name_type, name):
    assert re.match(r'^[\w]{6,64}$', name), '{} must be 6 - 64 alphanumeric characters'.format(name_type)

def is_valid_contract_name(name):
    _is_valid_name('Contract name', name)

def is_valid_author(name):
    _is_valid_name('Author', name)
