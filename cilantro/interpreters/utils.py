class RedisSerializer:
    @staticmethod
    def int(b: bytes):
        s = b.decode()
        i = int(s)
        return i

    @staticmethod
    def str(b: bytes):
        s = b.decode()
        return s

#class RedisExecutor:
