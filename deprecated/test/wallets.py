from deprecated.test.utils import *
from cilantro_ee.constants.system_config import *
from cilantro_ee.crypto import wallet


STU = ('db929395f15937f023b4682995634b9dc19b1a2b32799f1f67d6f080b742cdb1',
       '324ee2e3544a8853a3c5a0ef0946b929aa488cbe7e7ee31a0fef9585ce398502')
DAVIS = ('21fee38471799f8c2989dd81c6d46f6c2e2db6caf63efa98a093fcba064a4b62',
         'a103715914a7aae8dd8fddba945ab63a169dfe6e37f79b4a58bcf85bfd681694')
COLIN = ('9decc7f7f0b5a4fc87ab5ce700e2d6c5d51b7565923d50ea13cbf78031bb3acf',
         '20da05fdba92449732b3871cc542a058075446fedb41430ee882e99f9091cc4d')
FALCON = ('bac886e7c6e4a9fae572e170adb333b27b590157409e62d88cc0c7bc9a7b3631',
          'ed19061921c593a9d16875ca660b57aa5e45c811c8cf7af0cfcbd23faa52cbcd')
TJ = ('cf67a180f9578afa5fd704cea39b450c1542755d73614f6a4f41b627190b83bb',
      'cb9bfd4b57b243248796e9eb90bc4f0053d78f06ce68573e0fdca422f54bb0d2')
RAGHU = ('b44a8cc3dcadbdb3352ea046ec85cd0f6e8e3f584e3d6eb3bd10e142d84a9668',
         'c1f845ad8967b93092d59e4ef56aef3eba49c33079119b9c856a5354e9ccdf84')

COOL_KIDS = [STU, DAVIS, COLIN, FALCON, TJ, RAGHU]
GENERAL_WALLETS = []

if SHOULD_MINT_WALLET:
    for i in range(NUM_WALLETS_TO_MINT):
        sk, vk = wallet.new(int_to_padded_bytes(i))
        GENERAL_WALLETS.append((sk, vk))

#ALL_WALLETS = COOL_KIDS + GENERAL_WALLETS
ALL_WALLETS = COOL_KIDS
