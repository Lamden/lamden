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
            with open('data.pickle', 'wb') as f:
                pickle.dump(lt, f, pickle.HIGHEST_PROTOCOL)
                return f
        except Exception as e:
            print(e)
            return { 'error' : 'error' }

    @staticmethod
    def deserialize(p: pickle):
        try:
            with open(p, 'rb') as f:
                data = pickle.load(f)
                return data
        except Exception as e:
            print(e)
            return {'error': 'error'}

