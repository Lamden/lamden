from unittest import TestCase
from unittest import mock
from cilantro.storage.tables import build_tables
from seneca.smart_contract_user_libs import stdlib as std
from seneca.seneca_internal.storage.mysql_executer import Executer
from cilantro.storage.contracts import get_contract_exports

def contract(*contract_ids):
    def decorator(fn, *args, **kwargs):
        def test_fn(self):
            contracts = []
            for contract_id in contract_ids:
                if type(contract_id) in (tuple, list):
                    user_id, contract_id = contract_id
                    contracts.append(get_contract_exports(self.ex, self.tables.contracts, contract_id=contract_id, user_id=user_id))
                else:
                    contracts.append(get_contract_exports(self.ex, self.tables.contracts, contract_id=contract_id))
            return fn(self, *contracts)
        return test_fn
    return decorator

class SmartContractTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.ex = Executer('root', '', '', '127.0.0.1')
        self.tables = build_tables(self.ex, should_drop=True)

    def tearDown(self):
        super().tearDown()
        self.ex.cur.close()
        self.ex.conn.close()

def mock_datetime(target, datetime_module):
    class DatetimeSubclassMeta(type):
        @classmethod
        def __instancecheck__(mcs, obj):
            return isinstance(obj, std.datetime)

    class BaseMockedDatetime(std.datetime):
        @classmethod
        def now(cls, tz=None):
            return target.replace(tzinfo=tz)

        @classmethod
        def utcnow(cls):
            return target

        @classmethod
        def today(cls):
            return target

    MockedDatetime = DatetimeSubclassMeta('datetime', (BaseMockedDatetime,), {})

    return mock.patch.object(datetime_module, 'datetime', MockedDatetime)
