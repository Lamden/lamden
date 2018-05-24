# from unittest import TestCase
# from cilantro import Constants
#
# from cilantro.protocol.wallets import ED25519Wallet
# from cilantro.protocol.serialization import JSONSerializer
# from cilantro.protocol.proofs import SHA3POW
# from cilantro.protocol.transactions import Transaction
# from cilantro.protocol.interpreters import VanillaInterpreter
#
#
# class TestConstants(TestCase):
#     def test_protocol_constants(self):
#         self.assertTrue(Constants.Protocol.Wallets == ED25519Wallet)
#         self.assertTrue(Constants.Protocol.Serialization == JSONSerializer)
#         self.assertTrue(Constants.Protocol.Proofs == SHA3POW)
#         self.assertTrue(Constants.Protocol.Transactions == Transaction)
#         self.assertTrue(Constants.Protocol.Interpreters == VanillaInterpreter)
#
#     def test_mongo_constants(self):
#         self.assertTrue(Constants.MongoConstants.DbName == 'cilantro')
#         self.assertTrue(Constants.MongoConstants.BlocksColName == 'blockchain')
#         self.assertTrue(Constants.MongoConstants.LatestHashKey == 'latest_hash')
#         self.assertTrue(Constants.MongoConstants.LatestBlockNumKey == 'latest_block_num')
#         self.assertTrue(Constants.MongoConstants.BalancesColName == 'balances')
#         self.assertTrue(Constants.MongoConstants.GenesisKey == 'is_genesis')
#         self.assertTrue(Constants.MongoConstants.BlocksStateColName == 'blockchain_state')
#         self.assertTrue(Constants.MongoConstants.WalletKey == 'wallet')
#         self.assertTrue(Constants.MongoConstants.BalanceKey == 'balance')
#         self.assertTrue(Constants.MongoConstants.FaucetColName == 'faucet')
#
#     def test_node_top_level_constants(self):
#         self.assertTrue(Constants.Nodes.MaxRequestLength == 100000)
#         self.assertTrue(Constants.Nodes.MaxQueueSize == 4)
#         self.assertTrue(Constants.Nodes.QueueAutoFlushTime == 1.0)
#         self.assertTrue(Constants.Nodes.NtpUrl == "pool.ntp.org")
#         self.assertTrue(Constants.Nodes.FaucetPercent == 0.001)
#
#     def test_node_tx_status_constants(self):
#         self.assertTrue(Constants.Nodes.TxStatus.Success == "{} successfully published to the network")
#         self.assertTrue(Constants.Nodes.TxStatus.InvalidTxSize == "transaction exceeded max size")
#         self.assertTrue(Constants.Nodes.TxStatus.InvalidTxFields == "{}")
#         self.assertTrue(Constants.Nodes.TxStatus.SerializeFailed == "SERIALIZED_FAILED: {}")
#         self.assertTrue(Constants.Nodes.TxStatus.SendFailed == "Could not send transaction")
#
#     def test_masternode_constants(self):
#         self.assertTrue(Constants.Masternode.Host == "127.0.0.1")
#         self.assertTrue(Constants.Masternode.InternalPort == "9999")
#         self.assertTrue(Constants.Masternode.ExternalPort == "8080")
#
#     def test_witness_constants(self):
#         self.assertTrue(Constants.Witness.Host == "127.0.0.1")
#         self.assertTrue(Constants.Witness.SubPort == "9999")
#         self.assertTrue(Constants.Witness.PubPort == "8888")
#
#     def test_base_node_constants(self):
#         self.assertTrue(Constants.BaseNode.BaseUrl == "127.0.0.1")
#         self.assertTrue(Constants.BaseNode.SubscriberPort == "1111")
#         self.assertTrue(Constants.BaseNode.PublisherPort == "9998")
#
#     def test_delegate_constante(self):
#         self.assertTrue(Constants.Delegate.Host == "127.0.0.1")
#         self.assertTrue(Constants.Delegate.SubPort == "8888")
#         self.assertTrue(Constants.Delegate.PubPort == "7878")
#         self.assertTrue(Constants.Delegate.MasternodeUrl == "http://testnet.lamden.io:8080")
#         self.assertTrue(Constants.Delegate.GetBalanceUrl == "/balance/all")
#         self.assertTrue(Constants.Delegate.AddBlockUrl == "/add_block")
#         self.assertTrue(Constants.Delegate.GetUpdatesUrl == "/updates")
