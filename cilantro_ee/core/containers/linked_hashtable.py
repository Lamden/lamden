

class Node:
    def __init__(self, next, previous, key, value):
        self.next, self.previous, self.key, self.value = next, previous, key, value


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
        self._first, self._last = None, None
        self._table = dict()

    def __contains__(self, item):
        return item in self._table

    def __len__(self):
        return len(self._table)

    def clear(self):
        self._table.clear()
        self._first, self._last = None, None

    # the order of keys may not reflect the order of linked hash table
    def keys(self):
        return list(self._table.keys())

    def find(self, key):
        return True if key in self._table else False

    def insert_front(self, key, value):
        assert key not in self._table, "Attempted to insert key {} that is already in hash table keys {}".format(key, self._table)

        node = Node(next=self._first, previous=None, key=key, value=value)
        self._table[key] = node

        if self._first:
            self._first.previous = node
        self._first = node

        if not self._last:
            self._last = node

    def append(self, key, value):
        assert key not in self._table, "Attempted to insert key {} that is already in hash table keys {}".format(key, self._table)

        node = Node(next=None, previous=self._last, key=key, value=value)
        self._table[key] = node

        if self._last:
            self._last.next = node
        self._last = node

        if not self._first:
            self._first = node

    def pop_front(self):
        if not self._first:
            return None, None

        item = self._first
        if item.next:
            item.next.previous = None
        else:
            self._last = None
        self._first = item.next

        self._table.pop(item.key)
        return item.key, item.value

    def pop_back(self):
        if not self._last:
            return None

        item = self._last
        if item.previous:
            item.previous.next = None
        else:
            self._first = None
        self._last = item.previous

        self._table.pop(item.key)
        return item.key, item.value

    def remove(self, key):
        if key not in self._table:
            return

        item = self._table[key]

        if item.previous:
            item.previous.next = item.next
        else:
            assert item is self._first, "Key {} maps to item with no previous that is not self.first! item={}".format(key, item)
            return self.pop_front()

        if item.next:
            item.next.previous = item.previous
        else:
            assert item is self._last, "Key {} maps to item with no next that is not self.last! item={}".format(key, item)
            return self.pop_back()

        self._table.pop(key)
        return item.value



