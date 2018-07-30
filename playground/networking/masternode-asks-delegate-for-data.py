import secrets
import zmq
import asyncio
from cilantro.protocol.wallet import Wallet
import random

# generate random transactions
txs = [secrets.token_bytes(16) for i in range(64)]

# build a complete merkle tree
m = MerkleTree(txs)
h = m.hash_of_nodes()

# verify that the merkle tree can provide raw data provided a hash
t = [m.data_for_hash(h) for h in m.leaves]
print(txs == t)

# generate the delegates with new wallets
delegates = [Wallet.new() for i in range(64)]

connection_list = ['inproc://{}'.format(k[1]) for k in delegates]

# pretend to be a masternode by asking for pieces of data given a certain hash

# 1. masternode gets the hash of the merkle tree in its entirety
# 2. masternode gets a list of the nodes. added together, it should equal the hash
# 3. masternode gets a list of signatures of the hash (to do)
# 4. masternode asks all the delegates for pieces of the merkle root
# # a. given a list of delegates, randomly select one to ask for the chunk of data
# # b. if it fails, ask from another
# # c. repeat for X number of times (then trigger timeout?)
# # d. we should have all the data at this point

broadcasted_merkle_tree = m.merkle_leaves
broadcasted_merkle_leaves = m.merkle_leaves[len(m.merkle_leaves) // 2:]

correct_raw_data = [None for _ in range(len(m.merkle_leaves) // 2 + 1)]


def get_data_from_delegates():
    loop = asyncio.get_event_loop()
    context = zmq.Context()

    async def get_message(future, connection, h, i):
        request_socket = context.socket(socket_type=zmq.REQ)
        request_socket.connect(connection)
        request_socket.send(h)

        await asyncio.sleep(1)
        future.set_result(simulate_delegate_returning_chunk(h), i)

        request_socket.disconnect(connection)

    def verify_data(future):
        hsh, idx = future.result()
        if MerkleTree.hash(hsh) == broadcasted_merkle_leaves[idx] \
                and correct_raw_data is None:
            correct_raw_data[idx] = hsh

    tasks = []
    delegates_to_request = list(connection_list)
    for i in range(len(broadcasted_merkle_leaves)):
        shuffled_delegates = random.sample(delegates_to_request, k=len(delegates_to_request))
        for delegate in shuffled_delegates:
            f = asyncio.Future()
            f.add_done_callback(verify_data)
            tasks.append(get_message(*[f, delegate, i, broadcasted_merkle_leaves[i]]))

    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()


def simulate_delegate_returning_chunk(h, fail_rate=0.1):
    if random.random > fail_rate:
        return m.data_for_hash(h)
    else:
        return secrets.token_bytes(32)

get_data_from_delegates()
print(correct_raw_data)