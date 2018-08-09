

class Node:
    def __init__(self, next, previous, value):
        self.next, self.previous, self.value = next, previous, value


class LinkedHashTable:
    """
    This data structure is basically a hash table with a double linked list connecting the keys. Thus is behaves and
    looks very much like a traditional queue, except that it supports O(1) removals, at the cost of more space.
    In O(1) it supports:
        - Lookups (by key)
        - Adding to the front or back of queue
        - Popping from end of queue
        - Removing arbitary items from queue
    """

    def __init__(self):
        self.first, self.last = None, None
        self.table = dict()

    def __contains__(self, item):
        return item in self.table

    def append(self, key, value):
        assert key not in self.table, "Attempted to insert key {} that is already in hash table keys {}".format(key, self.table)

        node = Node(next=None, previous=self.last, value=value)
        self.table[key] = node

        if self.last:
            self.last.next = node
        self.last = node

        if not self.first:
            self.first = node

    def popleft(self):
        if not self.first:
            return None

        item = self.first
        if item.next:
            item.next.previous = None
        self.first = item.next

        return item.value

    def pop(self):
        if not self.last:
            return None

        item = self.last
        if item.previous:
            item.previous.next = None
        self.last = item.previous

        return item.value

    def remove(self, key):
        if key not in self.table:
            return

        item = self.table.pop(key)

        if item.previous:
            item.previous.next = item.next
        else:
            assert item is self.first, "Key {} maps to item with no previous that is not self.first! item={}".format(key, item)
            return self.popleft()

        if item.next:
            item.next.previous = item.previous
        else:
            assert item is self.last, "Key {} maps to item with no next that is not self.last! item={}".format(key, item)
            return self.pop()

        return item.value



