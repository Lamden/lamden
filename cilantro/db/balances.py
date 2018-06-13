from cilantro.logger import get_logger
from cilantro.db.contracts import execute_contract
from cilantro.db.tables import constitution_json


log = get_logger("Balance Seeder")


def seed_balances(executor):
    # TODO assert balances table is empty (we should only be seeding a fresh empty table)

    assert 'balances' in constitution_json, "Expected a key named 'balances' in constitution.json ... but it aint there"
    balances = constitution_json['balances']
    log.debug("Seeding {} wallets".format(len(balances)))

    for row in balances:
        wallet = row['wallet']
        amount = row['amount']

        log.debug("Seeding wallet {} with amount {}".format(wallet, amount))

        # TODO use currency contract to actually seed dat ish

