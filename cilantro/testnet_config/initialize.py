# takes a constitution file and seeds the state of the blockchain

import json
from cilantro.db.delegate import DB, DB_NAME
import os

j = json.load(open(os.path.join(os.path.dirname(__file__), 'constitution.json')))

with DB('{}_{}'.format(DB_NAME, 0)) as db:

    for k in j.keys():
        table_name = k
        t = getattr(db.tables, k)
        for item in j[k]:
            db.execute(t.insert(item))
