from cilantro.messages import MessageBaseJson


class Contract(MessageBaseJson):

    @classmethod
    def create(cls, user_id, contract_id, **kwargs):
        kwargs['user_id'] = user_id
        kwargs['contract_id'] = contract_id

        return cls.from_data(kwargs)

    def get_property(self, prop_name):
        return self._data.get(prop_name)
