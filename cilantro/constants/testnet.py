TESTNET_MASTERNODES = [
    {
        "sk": "06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a",
        "vk": "82540bb5a9c84162214c5540d6e43be49bbfe19cf49685660cab608998a65144",
        "ip":"72.29.1.1",
        "testnet-url": "tcp://127.0.0.1:11100"
    }
]

TESTNET_WITNESSES = [
    {
        "sk": "91f7021a9e8c65ca873747ae24de08e0a7acf58159a8aa6548910fe152dab3d8",
        "vk": "0e669c219a29f54c8ba4293a5a3df4371f5694b761a0a50a26bf5b50d5a76974",
        "ip":"72.29.2.1",
        "testnet-url": "tcp://127.0.0.1:21100"
    },
    {
        "sk": "f9489f880ef1a8b2ccdecfcad073e630ede1dd190c3b436421f665f767704c55",
        "vk": "50869c7ee2536d65c0e4ef058b50682cac4ba8a5aff36718beac517805e9c2c0",
        "ip":"72.29.2.2",
        "testnet-url": "tcp://127.0.0.1:21200"
    }
]

TESTNET_DELEGATES = [
    {
        "sk": "8ddaf072b9108444e189773e2ddcb4cbd2a76bbf3db448e55d0bfc131409a197",
        "vk": "3dd5291906dca320ab4032683d97f5aa285b6491e59bba25c958fc4b0de2efc8",
        "ip":"72.29.3.1",
        "testnet-url": "tcp://127.0.0.1:31100"
    },
    {
        "sk": "5664ec7306cc22e56820ae988b983bdc8ebec8246cdd771cfee9671299e98e3c",
        "vk": "ab59a17868980051cc846804e49c154829511380c119926549595bf4b48e2f85",
        "ip":"72.29.3.2",
        "testnet-url": "tcp://127.0.0.1:31200"
    },
    {
        "sk": "20b577e71e0c3bddd3ae78c0df8f7bb42b29b0c0ce9ca42a44e6afea2912d17b",
        "vk": "0c998fa1b2675d76372897a7d9b18d4c1fbe285dc0cc795a50e4aad613709baf",
        "ip":"72.29.3.3",
        "testnet-url": "tcp://127.0.0.1:31300"
    }
]

MAJORITY = 2

LOG_LEVEL = 21  # Just for debugging, so we can set the log level in one place for VMNet tests
