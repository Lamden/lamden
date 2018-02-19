MAX_REQUEST_LENGTH = 100000
MAX_QUEUE_SIZE = 4
QUEUE_AUTO_FLUSH_TIME = 1.0

TX_STATUS = {'SUCCESS': '{} successfully published to the network',
               'INVALID_TX_SIZE': 'transaction exceeded max size',
               'INVALID_TX_FIELDS': '{}',
               'SERIALIZE_FAILED': 'SERIALIZED_FAILED: {}',
               'SEND_FAILED': 'Could not send transaction'}

NTP_URL = 'pool.ntp.org'

# For faucet
FAUCET_WALLET = ('1680ee0c783bd70b039922b2c30ad9b4a54fe31509dde6405bd69d5a77e828a6',
                 '0415abadb5388a8484d612b1f175d8b501e144cb04792bb6107f5b7018c5f122')