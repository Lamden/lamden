#!/usr/bin/env seneca_0.1
## Example currency smart contract ##
# UNITTEST_FLAG_CURRENCY_SENECA 1729

import seneca.storage.tabular as st
import seneca.crypto as crypto
import seneca.runtime as rt
import seneca.stdlib as std
from seneca.modulelib import export, make_exports
import currency
import stake
import witness

CONTRACT = 'delegate'

t_delegates = st.create_table('delegate', [
    ('delegate_id', st.str_len(30), True)
])

kv_policy = kv.create_kv('constants')

@export
def stake():
    sender_id = rt.global_run_data.author
    assert witness.is_witness(), 'Please stake to become a witness first'
    stake_amount = stake.get('delegate_stake')
    currency.lock_coins(stake_amount, CONTRACT)
    t_delegates.insert([
        {'witneess_id':sender_id}
    ])

@export
def unstake():
    sender_id = rt.global_run_data.author
    currency.unlock_coins(CONTRACT)

@export
def get_vks(attr):
    return t_delegates.select()

exports = make_exports()
