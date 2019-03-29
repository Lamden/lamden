import datetime
from seneca.libs.storage.datatypes import Hash

# Declare Data Types
# this is at service contract level where it has registered wfc?  it's called 'loans' there ? and that returns loan_id (which is a simple int counter)


loan_apps = Hash('loan_applications', default_value=0)

@seneca_export
def get_config():
    return [('Customer_Name', 'str'), ('Amount': 'float2'), ('Length': 'integer'), ('Interest': 'float2')]

@seneca_export
def create(id, utc_time, config):
    assert id not in loan_apps, "Not a new loan application"
    # loan_apps['id'] = datetime.datetime.utcnow()    # creation time
    loan_apps['id'] = utc_time                        # caller sends it in so no consensus issues if needed
    for ckey, val in config:
        key = id + ':' + ckey
        loan_apps[key] = val
    # event published that new loan application created with loan_id: id
    # upon subscribing to this event scheduler and clients update their info using the apis below


@seneca_export
def get_state(id):
    pass      # return all keys and values as a list of tuples


@seneca_export
def get_value(id, key):
    pass      # the value of the key for the loan id

@seneca_export
def get_logic():
    pass      # this is the logic of the contract
    # approval <input list> <output>


@seneca_export
def get_task_set_to_run():
    pass
    # list will have:
    # schedule-time  task-name input-values including id, output key  -> events at the end of these tasks use <contractname:id> to publish
    #   "now" or (utc-time)
