MAX_REQUEST_LENGTH = 100000
MAX_QUEUE_SIZE = 1024

TX_STATUS = {'SUCCESS': {'status': '{} successfully published to the network'},
               'INVALID_TX_SIZE': {'status': 'error: transaction exceeded max size'},
               'INVALID_TX_FIELDS': {'status': 'error: transaction contains invalid fields'},
               'SERIALIZE_FAILED': {'status': 'Could not serialize transaction'},
               'SEND_FAILED': {'status': 'Could not send transaction'}}
