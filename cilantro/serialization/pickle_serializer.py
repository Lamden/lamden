import pickle
from cilantro.serialization import Serializer


'''
    PickleSerializer
    Used in block formation
    Turn tx list into byte object to hash in the process of delegate consensus 

'''

class PickleSerializer(Serializer):
    @staticmethod
    def serialize(lt: list):
        try:
            return pickle.dump(lt)
        except Exception as e:
            print(e)
            return { 'error' : 'error' }

    @staticmethod
    def deserialize(lt: list):
        try:
            return pickle.load(lt)
        except Exception as e:
            print(e)
            return {'error': 'error'}

