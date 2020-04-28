import hashlib


def merklize(leaves):
    # Make space for the parent hashes
    nodes = [None for _ in range(len(leaves) - 1)]

    # Hash all leaves so that all data is same length
    for l in leaves:
        h = hashlib.sha3_256()
        h.update(l)
        nodes.append(h.digest())

    # Hash each pair of leaves together and set the hash to their parent in the list
    for i in range((len(leaves) * 2) - 1 - len(leaves), 0, -1):
        h = hashlib.sha3_256()
        h.update(nodes[2 * i - 1] + nodes[2 * i])
        true_i = i - 1
        nodes[true_i] = h.digest()

    # Return the list
    return nodes


def verify_merkle_tree(leaves, expected_root):
    tree = merklize(leaves)

    if tree[0] == expected_root:
        return True
    return False
