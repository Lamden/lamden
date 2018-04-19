from cilantro import Constants
from decimal import Decimal


def validate_hex(hex_str, length=None, field_name="", raise_err=True):
    def handle_err(exp: Exception):
        if raise_err:
            raise exp
        return False

    try:
        int(hex_str, 16)
    except ValueError:
        return handle_err(Exception("Field {} was not valid hex with value={}".format(field_name, hex_str)))

    if length is None:
        pass
    elif len(hex_str) != length:
        return handle_err(Exception("Field {} was invalid in length. Expected length of {} but length was {}. "
                                    "Field value={}".format(field_name, length, len(hex_str), hex_str)))


def int_to_decimal(int_val):
    val = str(int_val)
    P = Constants.Protocol.DecimalPrecision
    return Decimal(str(val[0:-P]) + '.' + str(val[-P:]))
