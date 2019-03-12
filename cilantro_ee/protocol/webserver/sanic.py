from sanic import Sanic


class SanicSingleton(object):

    app = Sanic(__name__)

    def __enter__(self):
        return self.app

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def add_route(self, contract_id, fn_name, *args, **kwargs):
        # def fn():
        #     self.interface.execute_function(
        #         '{}.{}'.format(contract_id, fn_name), author, sender, stamps, *args, **kwargs)
        # app.add_route(fn, '/smart-contract/{}/{}'.format(contract_id, fn_name), methods=['POST'])
        pass
