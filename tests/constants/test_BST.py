"""
Helper Binary Search Tree for putting unit test modules execution into correct order

post order traversal used (going from leaves to root, or bottom up)
"""


class Node:
    def __init__(self, data):
        self.left = None
        self.right = None
        self.data = data

    def post_order_traversal(self, root, data=[]):
        if root:
            self.post_order_traversal(root.left, data=data)
            self.post_order_traversal(root.right, data=data)
            print(root.data)
            data.append(root.data)
            # yield root.data
        # else:
        #     return data
        print("data: {}".format(data))
