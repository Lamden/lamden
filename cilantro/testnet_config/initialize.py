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

    # add state for tables that are not masternodes and delegates as those get treated differently
    for k in j.keys():
        for item in j[k]:
            if k != 'masternodes' and k != 'delegates':
                t = getattr(db.tables, k)
                db.execute(t.insert(item))
            elif k == 'masternodes':
                masternodes.append(item)
            elif k == 'delegates':
                delegates.append(item)

    # sort masternodes and delegates lexigraphically for determinism

    t = getattr(db.tables, 'constants')
    db.execute(t.insert(get_policy_for_node_list(masternodes, 'masternodes')))
    db.execute(t.insert(get_policy_for_node_list(delegates, 'delegates')))
