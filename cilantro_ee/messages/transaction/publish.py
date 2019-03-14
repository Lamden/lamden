from cilantro_ee.messages.transaction.contract import ContractTransaction


class PublishTransaction(ContractTransaction):

    @classmethod
    def create(cls, sender_sk: str, stamps_supplied: int, contract_name: str, contract_code: str, nonce: str, **kwargs):
        # assert stamps_supplied > 0, "Must supply positive gas amount u silly billy"

        kwargs = {'contract_name': contract_name, 'code_str': contract_code}
        return super().create(sender_sk, stamps_supplied, 'smart_contract', 'submit_contract', nonce, kwargs)

    def __eq__(self, other):
        assert isinstance(other, ContractTransaction) or isinstance(other, PublishTransaction), "Publish tx cannot be " \
                                                                                                "compared with type {}".format(type(other))
        return self.to_dict() == other.to_dict()

