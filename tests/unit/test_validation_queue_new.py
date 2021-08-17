from unittest import TestCase

from lamden.nodes import validation_queue
from lamden.crypto.wallet import Wallet

import asyncio

def get_new_tx():
    return {
          "metadata": {
            "signature": "3cc0ad6c500b251b1d240dc57375c237f9160439fa3c1ccf737bec5aa175c99065f5e388660baf9d863c16d8ae8afd2a49752371aaa86d54c3a2480739011c06",
            "timestamp": 1625078664
          },
          "payload": {
            "contract": "currency",
            "function": "transfer",
            "kwargs": {
              "amount": {
                "__fixed__": "500000"
              },
              "to": "00b017b92efc32cb2e1d8ad52012370fde9332d14c712f702a2a512989a3032d"
            },
            "nonce": 0,
            "processor": "a9d0cbe69b7217c85bbf685c94ed00e0eb0960ae7742cf789422f92da6ba1c86",
            "sender": "45f943fb2a63ac12ef9321af33322e514a873589400247ad983d278fa8b450b1",
            "stamps_supplied": 100
          }
        }

def get_new_block(
        signer="92e45fb91c8f76fbfdc1ff2a58c2e901f3f56ec38d2f10f94ac52fcfa56fce2e",
        hash=None,
        number=1,
        hlc_timestamp='1'
):
    blockinfo = {
        "hash": hash or "0e0d0125ac8d23a28c88378777f78a138fe8e91f08ab91a63e9d754d49abd9bf",
        "number": number,
        "previous": "0000000000000000000000000000000000000000000000000000000000000000",
        "subblocks": [
          {
            "input_hash": "b48f385f46b2f836e878fdbc3e82d63cc747e92dd3df368b38424cd9aa230de5",
            "merkle_leaves": "3f4a582eb4b32b1a1f6568d70e6414743ea15fa673932d3075bbc3c9f9feed31",
            "signatures": [
              {
                "signature": "dc440f3db9cca56b41619aa9d55ec726ae30eb5e359d8954ee5d2692a54680218c59395547aaf8a556be655f8db99a7ea6d6a086b26d3210dbb0101472a7890b",
                "signer": signer
              }
            ],
            "subblock": 0,
            "transactions": [
              {
                "hash": "467ebaa7304d6bc9871ba0ef530e5e8b6dd7331f6c3ae7a58fa3e482c77275f3",
                "hlc_timestamp": hlc_timestamp,
                "result": "None",
                "stamps_used": 18,
                "state": [
                  {
                    "key": "currency.balances:45f943fb2a63ac12ef9321af33322e514a873589400247ad983d278fa8b450b1",
                    "value": {
                      "__fixed__": "287590566.1"
                    }
                  },
                  {
                    "key": "currency.balances:00b017b92efc32cb2e1d8ad52012370fde9332d14c712f702a2a512989a3032d",
                    "value": {
                      "__fixed__": "500000"
                    }
                  }
                ],
                "status": 0,
                "transaction": get_new_tx()
              }
            ]
          }
        ]
      }

    return blockinfo

class TestProcessingQueue(TestCase):
    def setUp(self):
        self.wallet = Wallet()

        self.running = True

        self.consensus_percent = 51
        self.num_of_peers = 0

        self.hard_apply_block_called = False
        self.set_peers_not_in_consensus_called = False
        self.rollback_called = False
        self.process_block_called = False

        self.current_block = 64 * f'0'

        self.validation_queue = validation_queue.ValidationQueue(
            wallet=self.wallet,
            consensus_percent=lambda: self.consensus_percent,
            get_peers_for_consensus=self.get_peers_for_consensus,
            process_from_consensus_result=self.process_from_consensus_result,
            hard_apply_block=self.hard_apply_block,
            set_peers_not_in_consensus=self.set_peers_not_in_consensus,
            is_next_block=self.is_next_block,
            rollback=self.rollback,
            stop_node=self.stop,
            testing=True
        )

        print("\n")

    def tearDown(self):
        self.validation_queue.stop()
        self.validation_queue.flush()

    def stop(self):
        self.running = False

    def get_peers_for_consensus(self):
        peers = {}
        for i in range(self.num_of_peers):
            peers[i] = i
        return peers

    def set_peers_not_in_consensus(self, ):
        self.set_peers_not_in_consensus = True

    async def rollback(self, consensus_hlc_timestamp=""):
        self.rollback_called = True

    def hard_apply_block(self, hlc_timestamp):
        self.hard_apply_block_called = True

    def process_from_consensus_result(self, block_info, hlc_timestamp):
        self.process_block_called = True

    def is_next_block(self, previous_block):
        return previous_block == self.current_block

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def add_solution(self, hlc_timestamp, verifying_key, hash=None):
        self.validation_queue.append(
            node_vk=verifying_key,
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=verifying_key, hash=hash),
            transaction_processed=get_new_tx()
        )

    def add_solutions(self, hlc_timestamp, amount=1, hash=None):
        for a in range(amount):
            self.add_solution(
                verifying_key=Wallet().verifying_key,
                hlc_timestamp=hlc_timestamp,
                hash=hash
            )

    def process_next(self):
        # Run process next, no consensus should be met as ideal is still possible
        tasks = asyncio.gather(
            self.validation_queue.process_next()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_get_solution_exists(self):
        hlc_timestamp = "1"
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash="1"),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        solution = self.validation_queue.get_solution(
            hlc_timestamp=hlc_timestamp,
            node_vk=self.wallet.verifying_key
        )

        self.assertIsNotNone(solution)

    def test_get_solution_hlc_DOES_NOT_exist(self):
        hlc_timestamp = "1"

        solution = self.validation_queue.get_solution(
            hlc_timestamp=hlc_timestamp,
            node_vk=Wallet().verifying_key
        )
        self.assertIsNone(solution)

    def test_get_solution_nodevk_DOES_NOT_exist(self):
        hlc_timestamp = "1"
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash="2"),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )
        solution = self.validation_queue.get_solution(
            hlc_timestamp=hlc_timestamp,
            node_vk=Wallet().verifying_key
        )

        self.assertIsNone(solution)

    def test_append(self):
        # These are solutions from me

        hlc_timestamp = "1"
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash="1"),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        solution = self.validation_queue.get_solution(
            hlc_timestamp=hlc_timestamp,
            node_vk=self.wallet.verifying_key
        )
        self.assertEqual("1", solution['hash'])

        self.assertEqual(len(self.validation_queue), 1)
        self.assertEqual(self.validation_queue[0], hlc_timestamp)

    def test_append_update(self):
        # These are solutions from me

        hlc_timestamp = "1"
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash="1"),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash="2"),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        solution = self.validation_queue.get_solution(
            hlc_timestamp=hlc_timestamp,
            node_vk=self.wallet.verifying_key
        )
        self.assertEqual("2", solution['hash'])

        self.assertEqual(len(self.validation_queue), 1)
        self.assertEqual(self.validation_queue[0], hlc_timestamp)

    def test_append(self):
        # These are solutions from peers

        hlc_timestamp = "1"
        peer_wallet = Wallet()

        # Add a peer solution
        self.add_solution(
            verifying_key=peer_wallet.verifying_key,
            hlc_timestamp=hlc_timestamp,
            hash="1"
        )

        solution = self.validation_queue.get_solution(
            hlc_timestamp=hlc_timestamp,
            node_vk=peer_wallet.verifying_key
        )
        self.assertEqual("1", solution['hash'])

    def test_append_update(self):
        # These are solutions from peers
        # Updated stored solution for a peer when update is received

        hlc_timestamp = "1"
        peer_wallet = Wallet()

        # Add a peer solution
        self.add_solution(
            verifying_key=peer_wallet.verifying_key,
            hlc_timestamp=hlc_timestamp,
            hash="1"
        )

        # Add a peer solution
        self.add_solution(
            verifying_key=peer_wallet.verifying_key,
            hlc_timestamp=hlc_timestamp,
            hash="2"
        )

        solution = self.validation_queue.get_solution(
            hlc_timestamp=hlc_timestamp,
            node_vk=peer_wallet.verifying_key
        )
        self.assertEqual("2", solution['hash'])

    def test_append_ignore_older_than_consensus(self):
        # These are solutions from peers
        # Updated stored solution for a peer when update is received

        self.validation_queue.last_hlc_in_consensus = "2"
        hlc_timestamp = "1"
        peer_wallet = Wallet()

        # Add a peer solution
        self.add_solution(
            verifying_key=peer_wallet.verifying_key,
            hlc_timestamp=hlc_timestamp,
            hash="1"
        )

        solution = self.validation_queue.get_solution(
            hlc_timestamp=hlc_timestamp,
            node_vk=peer_wallet.verifying_key
        )

        self.assertIsNone(solution)

    def test_awaiting_validation(self):
        hlc_timestamp = "1"
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        self.assertTrue(self.validation_queue.awaiting_validation(hlc_timestamp))
        self.assertIsNotNone(self.validation_queue.validation_results[hlc_timestamp]['solutions'][self.wallet.verifying_key])

    def test_get_consensus_result(self):
        solutions = {
            '1': {
                'hash': 'incorrect',
                'pass': False
            },
            '2': {
                'hash': 'correct',
                'pass': True
            }
        }
        consensus_result = self.validation_queue.get_consensus_result(
            solutions=solutions,
            consensus_solution="correct"
        )
        self.assertTrue(consensus_result['pass'])

    def test_process_next_no_consensus(self):
        hlc_timestamp = "1"
        self.num_of_peers = 1  # Does not include me

        # Add our result to the validation results object
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        # Await the the queue attempting consensus
        self.process_next()

        self.assertFalse(self.hard_apply_block_called)
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, "")

    def test_process_ideal_consensus(self):
        hlc_timestamp = "1"
        self.num_of_peers = 1  # Does not include me

        # Add our result to the validation results object
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        # Add another solution to the validation results object
        self.add_solutions(hlc_timestamp)

        self.async_sleep(0.1)
        # Await the the queue attempting consensus
        self.process_next()

        self.assertTrue(self.hard_apply_block_called)
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, hlc_timestamp)
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_next_ideal_consensus_on_updated_information_from_me(self):
        hlc_timestamp = "1"
        self.num_of_peers = 2  # Does not include me

        # Add our result to the validation results object
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash="1"),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        # Add another solution to the validation results object
        self.add_solutions(hlc_timestamp, hash="2")

        # Process the validation queue
        self.process_next()

        # Not currently in consensus
        self.assertFalse(self.hard_apply_block_called)
        self.assertEqual("", self.validation_queue.last_hlc_in_consensus)

        # Change our solution and re-append
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash="2"),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        # Process the validation queue again
        self.process_next()

        # Now we have consensus
        self.assertTrue(self.hard_apply_block_called)
        self.assertEqual(hlc_timestamp, self.validation_queue.last_hlc_in_consensus)

    def test_process_next_ideal_consensus_on_updated_information_from_peer(self):
        hlc_timestamp = "1"
        self.num_of_peers = 2  # Does not include me

        # Add our result to the validation results object
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash="1"),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        peer_wallet = Wallet()

        # Add a peer solution
        self.add_solution(
            verifying_key=peer_wallet.verifying_key,
            hlc_timestamp=hlc_timestamp,
            hash="2"
        )

        # Process the validation queue
        self.process_next()

        # Not currently in consensus
        self.assertFalse(self.hard_apply_block_called)
        self.assertEqual("", self.validation_queue.last_hlc_in_consensus)

        # Add an updated solution from a peer
        self.add_solution(
            verifying_key=peer_wallet.verifying_key,
            hlc_timestamp=hlc_timestamp,
            hash="1"
        )

        # Process the validation queue again
        self.process_next()

        # Now we have consensus
        self.assertTrue(self.hard_apply_block_called)
        self.assertEqual(hlc_timestamp, self.validation_queue.last_hlc_in_consensus)

    def test_process_next_ideal_consensus_matches_me(self):
        '''
            Ideal consensus test setup will have 2 nodes both of which are in consensus
            I will be one of the 2 nodes in the consensus group so I should hard apply and move on
        '''
        hlc_timestamp = "1"
        self.num_of_peers = 1  # Does not include me

        # Add our result to the validation results object
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        # Add another solution to the validation results object
        self.add_solutions(hlc_timestamp)

        # Await the the queue attempting consensus
        self.process_next()

        # Test that consensus was achieved and we are in it
        # Hard apply was called
        self.assertTrue(self.hard_apply_block_called)
        # hlc_timestamp was marked as last_hlc_in_consensus
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, hlc_timestamp)
        # All results deleted from validation_results object
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_next_ideal_consensus_DOES_NOT_match_me(self):
        '''
            Ideal consensus test setup will have 3 nodes two on consensus and 1 is not
            I will be the 1 node out of consensus which means I should detect ideal consensus and then call rollback.
        '''
        hlc_timestamp = "1"
        self.num_of_peers = 1  # Does not include me

        # Add our result to the validation results object
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash='1'),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        # Add another 2 solutions which are both in consensus
        self.add_solutions(hlc_timestamp, amount=2)

        # Await the the queue attempting consensus
        self.process_next()

        # validation queue should process consensus and I am out of consensus
        # rollback is called
        self.assertTrue(self.rollback_called)
        # hard apply is not called
        self.assertTrue(self.hard_apply_block_called)
        # hlc_timestamp was not set as last_hlc_in_consensus
        self.assertEqual('1', self.validation_queue.last_hlc_in_consensus)
        # results are NOT removed from the validation_results object
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_ideal_consensus_MISSING_me(self):
        '''
            Ideal consensus test setup will have 3 nodes two in consensus and I will not provide a solution
            Consensus should still conclude even though I don't provide a solution.
        '''
        hlc_timestamp = "1"
        self.num_of_peers = 2  # Does not include me

        # Add another 2 solutions which are both in consensus
        self.add_solutions(hlc_timestamp, amount=2)

        # Await the the queue attempting consensus
        self.process_next()

        # Hard apply was called
        self.assertTrue(self.hard_apply_block_called)
        # hlc_timestamp was marked as last_hlc_in_consensus
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, hlc_timestamp)
        # All results deleted from validation_results object
        self.assertFalse(self.validation_queue.awaiting_validation(hlc_timestamp))

    def test_process_next_eager_consensus_matches_me(self):
        '''
            Eager consensus test setup will have 4 nodes. Two are in consensus and the other two differ from consensus
            and each other.
            This is a 50% consensus and the validation queue should decide on eager consensus only when all 4 results
            are in.
            I will be in the consensus group so I should hard apply and move on
        '''
        hlc_timestamp = "1"
        self.num_of_peers = 3  # Does not include me

        # Add our result to the validation results object (will have a non-consensus hash)
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        # Add another result which matches me
        self.add_solutions(hlc_timestamp)

        # Add another result that is out of consensus
        self.add_solutions(hlc_timestamp, hash="1", amount=1)

        # Run process next, no consensus should be met as ideal is still possible
        self.process_next()

        # Make sure consensus wasn't reached
        self.assertFalse(self.hard_apply_block_called)
        self.assertFalse(self.rollback_called)
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, "")
        # Make sure ideal consensus is still possible
        self.assertTrue(self.validation_queue.check_ideal_consensus_possible(hlc_timestamp))

        # Add another result that is out of consensus and also matches no one
        self.add_solutions(hlc_timestamp, hash="2", amount=1)

        # Run process next. All peers are in and only 50% are in consensus. Eager consensus is expected
        self.assertEqual(4, self.validation_queue.check_num_of_solutions(hlc_timestamp))
        self.process_next()

        # validation queue should process consensus
        # hard apply is called
        self.assertTrue(self.hard_apply_block_called)
        # hlc_timestamp is marked as last_hlc_in_consensus
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, hlc_timestamp)
        # all results are deleted from the validation_results object
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_next_eager_consensus_DOES_NOT_match_me(self):
        '''
            Eager consensus test setup will have 4 nodes. Two are in consensus and the other two differ from consensus
            and each other.
            This is a 50% consensus and the validation queue should decide on eager consensus only when all 4 results
            are in.
            I will be in the group that differs so I should attempt to rollback after eager consensus is determined
        '''
        hlc_timestamp = "1"
        self.num_of_peers = 3  # Does not include me

        # Add our result to the validation results object (will have a non-consensus hash)
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash='1'),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        # Add another two results that match each other but not me
        self.add_solutions(hlc_timestamp, amount=2)

        # Run process next, no consensus should be met as ideal is still possible
        self.process_next()

        # Make sure consensus wasn't reached
        self.assertFalse(self.hard_apply_block_called)

        self.assertFalse(self.rollback_called)
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, "")

        # Make sure ideal consensus is still possible
        self.assertTrue(self.validation_queue.check_ideal_consensus_possible(hlc_timestamp))

        # Add another result that is out of consensus and also matches no one else
        self.add_solutions(hlc_timestamp, hash="2", amount=1)

        # Run process next. All peers are in and only 50% are in consensus. Eager consensus is expected
        self.assertEqual(4, self.validation_queue.check_num_of_solutions(hlc_timestamp))
        self.process_next()

        # validation queue should process consensus and I am out of consensus
        # hard apply is called
        self.assertTrue(self.hard_apply_block_called)
        # Rollback is called
        self.assertTrue(self.rollback_called)
        # hlc_timestamp was not set as last_hlc_in_consensus
        self.assertEqual('1', self.validation_queue.last_hlc_in_consensus)
        # results are not removed from the validation_results object
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_next_failed_consensus_matches_me(self):
        '''
            Failed consensus setup will have 3 nodes all with different solutions.
            I will have the top solution when determining higher numerical hex value
        '''
        hlc_timestamp = "1"
        self.num_of_peers = 2  # Does not include me

        # Add our result to the validation results object (will have a non-consensus hash)
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash="1"),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        # Add another result which does not match me
        self.add_solutions(hlc_timestamp, hash="2")

        # Add another result which does not match anyone
        self.add_solutions(hlc_timestamp, hash="3")

        # Run process next, no consensus should be met as ideal is still possible
        self.process_next()

        # validation queue should process consensus
        # hard apply is called
        self.assertTrue(self.hard_apply_block_called)
        # hlc_timestamp is marked as last_hlc_in_consensus
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, hlc_timestamp)
        # all results are deleted from the validation_results object
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_next_failed_consensus_DOES_NOT_match_me(self):
        '''
            Failed consensus setup will have 3 nodes all with different solutions.
            I will NOT have the top solution when determining higher numerical hex value
        '''
        hlc_timestamp = "1"
        self.num_of_peers = 2  # Does not include me

        # Add our result to the validation results object (will have a non-consensus hash)
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash="2"),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        # Add another result which does not match me
        self.add_solutions(hlc_timestamp, hash="1")

        # Add another result which does not match anyone
        self.add_solutions(hlc_timestamp, hash="3")

        # Run process next, no consensus should be met as ideal is still possible
        self.process_next()

        # validation queue should process consensus and I am out of consensus
        # rollback is called
        self.assertTrue(self.rollback_called)
        # hard apply is not called
        self.assertTrue(self.hard_apply_block_called)
        # hlc_timestamp was not set as last_hlc_in_consensus
        self.assertEqual('1', self.validation_queue.last_hlc_in_consensus)
        # results are not removed from the validation_results object
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_fall_through_from_ideal_to_failure(self):
        '''
            This test will add results and process after each one. Making sure the validation queue can swtch between
            the consensus types as new info comes in.
        '''
        hlc_timestamp = "1"
        self.num_of_peers = 3  # Does not include me

        # Add 1 of 4 results to the validation results object and process next
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash="1"),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )
        self.process_next()
        self.assertTrue(self.validation_queue.check_ideal_consensus_possible(hlc_timestamp))
        self.assertTrue(self.validation_queue.check_eager_consensus_possible(hlc_timestamp))

        # Add 2 of 4 results to the validation results object and process next
        self.add_solutions(hlc_timestamp, hash="2")
        self.process_next()
        self.assertTrue(self.validation_queue.check_ideal_consensus_possible(hlc_timestamp))
        self.assertTrue(self.validation_queue.check_eager_consensus_possible(hlc_timestamp))

        # Add 3 of 4 results to the validation results object and process next
        self.add_solutions(hlc_timestamp, hash="1")
        self.process_next()
        self.assertTrue(self.validation_queue.check_ideal_consensus_possible(hlc_timestamp))
        self.assertTrue(self.validation_queue.check_eager_consensus_possible(hlc_timestamp))

        # Add 4 of 4 results to the validation results object and process next
        self.add_solutions(hlc_timestamp, hash="2")
        self.process_next()
        self.assertFalse(self.validation_queue.check_ideal_consensus_possible(hlc_timestamp))
        self.assertFalse(self.validation_queue.check_eager_consensus_possible(hlc_timestamp))

        # hard apply is not called
        self.assertTrue(self.hard_apply_block_called)

    def test_tally_solutions(self):
        hlc_timestamp='1'
        # Add our result to the validation results object (will have a non-consensus hash)
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash="1"),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        # Add some nodes with a particular result
        self.add_solutions(hlc_timestamp, hash="3", amount=3)

        # Add some more nodes with another result
        self.add_solutions(hlc_timestamp, hash="2", amount=2)

        tally = self.validation_queue.tally_solutions(
            solutions=self.validation_queue.validation_results[hlc_timestamp]['solutions']
        )

        self.assertEqual(1, tally['tallies']['1'])
        self.assertEqual(2, tally['tallies']['2'])
        self.assertEqual(3, tally['tallies']['3'])

        for result in tally['results_list']:
            self.assertEqual(result['consensus_amount'], int(result['solution']))

        self.assertEqual(1, len(tally['top_solutions_list']))
        self.assertEqual('3', tally['top_solutions_list'][0]['solution'])
        self.assertEqual(3, tally['top_solutions_list'][0]['consensus_amount'])

        self.assertFalse(tally['is_tied'])

    def test_tally_solutions_tied(self):
        hlc_timestamp='1'
        # Add our result to the validation results object (will have a non-consensus hash)
        self.validation_queue.append(
            hlc_timestamp=hlc_timestamp,
            block_info=get_new_block(signer=self.wallet.verifying_key, hash="1"),
            transaction_processed=get_new_tx(),
            node_vk=self.wallet.verifying_key
        )

        # Add some nodes with a particular result
        self.add_solutions(hlc_timestamp, hash="3", amount=2)

        # Add some more nodes with another result
        self.add_solutions(hlc_timestamp, hash="2", amount=2)

        tally = self.validation_queue.tally_solutions(
            solutions=self.validation_queue.validation_results[hlc_timestamp]['solutions']
        )

        self.assertEqual(1, tally['tallies']['1'])
        self.assertEqual(2, tally['tallies']['2'])
        self.assertEqual(2, tally['tallies']['3'])

        self.assertEqual(2, len(tally['top_solutions_list']))

        self.assertEqual('3', tally['top_solutions_list'][0]['solution'])
        self.assertEqual(2, tally['top_solutions_list'][0]['consensus_amount'])

        self.assertEqual('2', tally['top_solutions_list'][1]['solution'])
        self.assertEqual(2, tally['top_solutions_list'][1]['consensus_amount'])

        self.assertTrue(tally['is_tied'])

    def test_check_ideal_consensus_no_consensus_ideal_still_possible(self):
        # test assumption for consensus:
        # number of peers = 10
        # consensus % = 51

        tally_info = {
             'results_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 5
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 4
                 }
             ]
        }
        solutions_missing = 1
        consensus_needed = 6

        ideal_consensus_results = self.validation_queue.check_ideal_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertFalse(ideal_consensus_results['has_consensus'])
        self.assertTrue(ideal_consensus_results['ideal_consensus_possible'])

    def test_check_ideal_consensus_no_consensus_ideal_not_possible(self):
        # test assumption for consensus:
        # number of peers = 10
        # consensus % = 51

        tally_info = {
             'results_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 4
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 3
                 },
                 {
                     'solution': '3',
                     'consensus_amount': 3
                 }
             ]
        }
        solutions_missing = 1
        consensus_needed = 6

        ideal_consensus_results = self.validation_queue.check_ideal_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertFalse(ideal_consensus_results['has_consensus'])
        self.assertFalse(ideal_consensus_results['ideal_consensus_possible'])

    def test_check_ideal_consensus_has_consensus_matches_me(self):
        # test assumption for consensus:
        # number of peers = 10
        # consensus % = 51

        tally_info = {
             'results_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 6
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 3
                 }
             ]
        }
        solutions_missing = 1
        consensus_needed = 6

        ideal_consensus_results = self.validation_queue.check_ideal_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertTrue(ideal_consensus_results['matches_me'])
        self.assertTrue(ideal_consensus_results['has_consensus'])
        self.assertTrue(ideal_consensus_results['ideal_consensus_possible'])
        self.assertEqual('ideal', ideal_consensus_results['consensus_type'])
        self.assertEqual('1', ideal_consensus_results['solution'])
        self.assertEqual('1', ideal_consensus_results['my_solution'])

    def test_check_ideal_consensus_has_consensus_DOES_NOT_match_me(self):
        # test assumption for consensus:
        # number of peers = 10
        # consensus % = 51

        tally_info = {
             'results_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 6
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 3
                 }
             ]
        }
        solutions_missing = 1
        consensus_needed = 6

        ideal_consensus_results = self.validation_queue.check_ideal_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="2"
        )

        self.assertFalse(ideal_consensus_results['matches_me'])
        self.assertTrue(ideal_consensus_results['has_consensus'])
        self.assertTrue(ideal_consensus_results['ideal_consensus_possible'])
        self.assertEqual('ideal', ideal_consensus_results['consensus_type'])
        self.assertEqual('1', ideal_consensus_results['solution'])
        self.assertEqual('2', ideal_consensus_results['my_solution'])

    def test_check_eager_consensus_no_consensus_eager_still_possible(self):
        # test assumption for consensus:
        # number of peers = 20
        # consensus % = 51

        tally_info = {
            'is_tied': True,
            'results_list': [
                {
                     'solution': '1',
                     'consensus_amount': 9
                },
                {
                     'solution': '2',
                     'consensus_amount': 9
                },
                {
                    'solution': '3',
                    'consensus_amount': 1
                }
            ]
        }
        solutions_missing = 1
        consensus_needed = 11

        eager_consensus_results = self.validation_queue.check_eager_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertFalse(eager_consensus_results['has_consensus'])
        self.assertTrue(eager_consensus_results['eager_consensus_possible'])

    def test_check_eager_consensus_no_consensus_eager_not_possible(self):
        # test assumption for consensus:
        # number of peers = 20
        # consensus % = 51

        tally_info = {
            'is_tied': True,
            'results_list': [
                {
                    'solution': '1',
                    'consensus_amount': 10
                },
                {
                    'solution': '2',
                    'consensus_amount': 10
                }
            ]
        }
        solutions_missing = 0
        consensus_needed = 11

        eager_consensus_results = self.validation_queue.check_eager_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertFalse(eager_consensus_results['has_consensus'])
        self.assertFalse(eager_consensus_results['eager_consensus_possible'])

    def test_check_eager_consensus_has_consensus_matches_me(self):
        # test assumption for consensus:
        # number of peers = 20
        # consensus % = 51

        tally_info = {
            'is_tied': False,
            'results_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 10
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 8
                 },
                 {
                     'solution': '3',
                     'consensus_amount': 1
                 }
            ],
        }
        solutions_missing = 1
        consensus_needed = 11

        eager_consensus_results = self.validation_queue.check_eager_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertTrue(eager_consensus_results['matches_me'])
        self.assertTrue(eager_consensus_results['has_consensus'])
        self.assertTrue(eager_consensus_results['eager_consensus_possible'])
        self.assertEqual('eager', eager_consensus_results['consensus_type'])
        self.assertEqual('1', eager_consensus_results['solution'])
        self.assertEqual('1', eager_consensus_results['my_solution'])

    def test_check_eager_consensus_has_consensus_DOES_NOT_match_me(self):
        # test assumption for consensus:
        # number of peers = 20
        # consensus % = 51

        tally_info = {
            'is_tied': False,
            'results_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 10
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 8
                 },
                 {
                     'solution': '3',
                     'consensus_amount': 1
                 }
            ]
        }
        solutions_missing = 1
        consensus_needed = 11

        eager_consensus_results = self.validation_queue.check_eager_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="2"
        )

        self.assertFalse(eager_consensus_results['matches_me'])
        self.assertTrue(eager_consensus_results['has_consensus'])
        self.assertTrue(eager_consensus_results['eager_consensus_possible'])
        self.assertEqual('eager', eager_consensus_results['consensus_type'])
        self.assertEqual('1', eager_consensus_results['solution'])
        self.assertEqual('2', eager_consensus_results['my_solution'])

    def test_check_failed_consensus_matches_me(self):
        # test assumption for consensus:
        # number of peers = 20
        # consensus % = 51

        tally_info = {
            'top_solutions_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 10
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 10
                 }
            ]
        }

        consensus_needed = 11

        failed_consensus_results = self.validation_queue.check_failed_consensus(
            tally_info=tally_info,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertTrue(failed_consensus_results['matches_me'])
        self.assertTrue(failed_consensus_results['has_consensus'])
        self.assertEqual('failed', failed_consensus_results['consensus_type'])
        self.assertEqual('1', failed_consensus_results['solution'])
        self.assertEqual('1', failed_consensus_results['my_solution'])

    def test_check_failed_consensus_DOES_NOT_match_me(self):
        # test assumption for consensus:
        # number of peers = 20
        # consensus % = 51

        tally_info = {
            'top_solutions_list': [
                {
                    'solution': '1',
                    'consensus_amount': 10
                },
                {
                    'solution': '2',
                    'consensus_amount': 10
                }
            ]
        }

        consensus_needed = 11

        failed_consensus_results = self.validation_queue.check_failed_consensus(
            tally_info=tally_info,
            consensus_needed=consensus_needed,
            my_solution="2"
        )

        self.assertFalse(failed_consensus_results['matches_me'])
        self.assertTrue(failed_consensus_results['has_consensus'])
        self.assertEqual('failed', failed_consensus_results['consensus_type'])
        self.assertEqual('1', failed_consensus_results['solution'])
        self.assertEqual('2', failed_consensus_results['my_solution'])

    def test_clear_my_solutions(self):
        self.validation_queue.validation_results = {
            'hlc_1': {
                'solutions': {
                    self.validation_queue.wallet.verifying_key: 'solution',
                    '2': 'solution'
                }
            },
            'hlc_2': {
                'solutions': {
                    self.validation_queue.wallet.verifying_key: 'solution'
                }
            },
            'hlc_3': {
                'solutions': {
                    '2': 'solution'
                }
            }
            ,
            'hlc_4': {
                'solutions': {}
            }
        }
        self.validation_queue.clear_my_solutions()

        self.assertIsNone(self.validation_queue.validation_results['hlc_1']['solutions'].get(self.validation_queue.wallet.verifying_key))
        self.assertIsNotNone(self.validation_queue.validation_results['hlc_1']['solutions'].get('2'))

        self.assertIsNone(self.validation_queue.validation_results['hlc_2']['solutions'].get(self.validation_queue.wallet.verifying_key))

        self.assertIsNone(self.validation_queue.validation_results['hlc_3']['solutions'].get(self.validation_queue.wallet.verifying_key))
        self.assertIsNotNone(self.validation_queue.validation_results['hlc_3']['solutions'].get('2'))