def sketch():
    import redis, time
    from pymongo import MongoClient
    r = redis.StrictRedis()
    redis_ready = False
    mongo_ready = False
    while not redis_ready or not mongo_ready:
        try:
            r.client_list()
            redis_ready = True
        except:
            print("Waiting for Redis to be ready...")
        try:
            MongoClient()
            mongo_ready = True
        except:
            print("Waiting for Mongo to be ready...")
        time.sleep(1)

