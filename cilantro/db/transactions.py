from cilantro.logger import get_logger
import seneca.seneca_internal.storage.easy_db as t
from cilantro.db.tables import create_table


def build_transactions_table(ex, should_drop=True):
    transactions = t.Table('transactions',
                           t.Column('hash', t.str_len(64), True),
                           [
                               t.Column('data', str),
                               t.Column('block_hash', t.str_len(64)),  # TODO how to index this column?
                           ])
    return create_table(ex, transactions, should_drop)


def seed_transactions(ex, transactions_table):
    # Currently we are not seeding any transactions, but I provide this API for uniformity
    pass
