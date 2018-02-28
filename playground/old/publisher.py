from cilantro.protocol.serialization import JSONSerializer

if __name__ == '__main__':
    try:
        JSONSerializer.serialize()
    except Exception as e:
        print(e)


