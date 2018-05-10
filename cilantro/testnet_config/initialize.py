# takes a constitution file and seeds the state of the blockchain

import json
from cilantro.db.delegate import DB, DB_NAME
import os


def get_policy_for_node_list(l, name):
    payload = ''.join(sorted(l))
    p = {
        "policy": name,
        "type": "multi_discrete",
        "last_election": 0,
        "election_length": 168,
        "election_frequency": 336,
        "max_votes": 0,
        "value": payload,
        "round": 0
    }
    return p


j = json.load(open(os.path.join(os.path.dirname(__file__), 'constitution.json')))

with DB('{}_{}'.format(DB_NAME, 0)) as db:

    masternodes = []
    delegates = []
    witnesses = []

    # add state for tables that are not masternodes and delegates as those get treated differently
    for k in j.keys():
        for item in j[k]:
            if k != 'masternodes' and k != 'delegates' and k != 'witnesses':
                t = getattr(db.tables, k)
                db.execute(t.insert(item))
            elif k == 'masternodes':
                masternodes.append(item)
            elif k == 'delegates':
                delegates.append(item)
            elif k == 'witnesses':
                witnesses.append(item)

    # add the masternodes and delegates to the policy table. this is so that users can easily add wallets to the
    # constitution and
    t = getattr(db.tables, 'constants')
    db.execute(t.insert(get_policy_for_node_list(masternodes, 'masternodes')))
    db.execute(t.insert(get_policy_for_node_list(delegates, 'delegates')))
    db.execute(t.insert(get_policy_for_node_list(witnesses, 'witnesses')))
