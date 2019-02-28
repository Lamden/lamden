from cilantro_ee.storage.contracts import run_contract, get_contract_exports


"""
Utilities for testing smart contracts and Seneca interpreter
"""


def test_contract(*contract_ids):
    """
    A decorator for testing smart contracts. This works by passing the decorated function an object cabable of invoking
    read-only forms of all @export decorated method within the smart contract.

    # TODO better docstring

    :param contract_ids:
    :return:

    Example using tuples and multiple contracts:

    @test_contract(
        ('DAVIS', 'currency'),
        ('FALCON', 'currency')
    )
    def test_transfer_coins(self, davis, falcon):
        davis.transfer_coins('FALCON', 47)
        self.assertEqual(davis.get_balance('DAVIS'), 3696900)
        self.assertEqual(davis.get_balance('FALCON'), 47)

    Example using a single contract with no user id

    @contract('currency')
    def test_create_wallet(self, currency):
        currency.create_wallet('MumboJumbo')
        self.assertTrue(currency.wallet_exists('MumboJumbo'))
    """
    def decorator(fn, *args, **kwargs):
        def test_fn(self):
            assert hasattr(self, 'contracts_table'), "Use of this decorator expects 'self' to have a property " \
                                                     "'contracts_table', which references the contracts table built by " \
                                                     "build_contracts_table in storage/contracts.py"
            contracts = []

            for contract_id in contract_ids:
                if type(contract_id) in (tuple, list):
                    user_id, contract_id = contract_id
                    contracts.append(get_contract_exports(self.ex, self.contracts_table, contract_id=contract_id, user_id=user_id))
                else:
                    contracts.append(get_contract_exports(self.ex, self.contracts_table, contract_id=contract_id))

            return fn(self, *contracts)
        return test_fn
    return decorator