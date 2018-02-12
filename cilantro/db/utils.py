class RedisSerializer:
    @staticmethod
    def int(b: bytes):
        try:
            s = b.decode()
            i = int(s)
        except:
            if b == None:
                i = 0
        return i

    @staticmethod
    def str(b: bytes):
        s = b.decode()
        return s

    @staticmethod
    def dict(d: dict):
        new_d = {}
        for k, v in d.items():
            new_d[k.decode()] = v.decode()
        return new_d
