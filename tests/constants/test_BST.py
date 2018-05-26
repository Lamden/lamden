"""
Helper Binary Search Tree for putting unit test modules execution into correct order

post order traversal used (going from leaves to root, or bottom up)
"""


class Node:
    def __init__(self, data):
        self.left = None
        self.right = None
        self.data = data

    def post_order_traversal(self, root):
        if root:
            self.post_order_traversal(root.left)
            self.post_order_traversal(root.right)
            yield(root.data)

