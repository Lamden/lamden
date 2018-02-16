MAX_REQUEST_LENGTH = 100000
MAX_QUEUE_SIZE = 1024

TX_STATUS = {'SUCCESS': '{} successfully published to the network',
               'INVALID_TX_SIZE': 'transaction exceeded max size',
               'INVALID_TX_FIELDS': '{}',
               'SERIALIZE_FAILED': 'SERIALIZED_FAILED: {}',
               'SEND_FAILED': 'Could not send transaction'}

NTP_URL = 'pool.ntp.org'