"""
Here we provide augmented data structures, namely a set and a dict, which have an upper bound or 'cap' on the number of
elements they can contain. Once this cap is reached, elements are deleted FIFO.

From the outside, these containers have exactly the same API as their parents.
"""
from collections import OrderedDict, deque


class CappedDict(OrderedDict):
    def __init__(self, max_size=65536, name='', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_size = max_size

    def __setitem__(self, *args, **kwargs):
        if len(self) >= self.max_size:
            self.popitem(last=False)

        super().__setitem__(*args, **kwargs)


"""
TODO --
For performance, this CappedSet should be swapped out with a bloom filter. Only tricky bit is figuring out how to 
delete the old entries after a max size is reached. Over we could create create bloom filters ever n units of time,
but after each n/2 unit of time create a new bloom filter, and "swap" out the bloom filter at c*n with the dupe that was
created at c*n - c*n/2 (for some constant c). Then we can effectively create this desired behavior by having 2 bloom 
filters in RAM. For like 2^64 bit bloom filter, 2 * 2^64 is not bad overhead. 
"""
class CappedSet(set):
    def __init__(self, max_size=65536, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_size = max_size
        self.fifo_queue = deque()

    def add(self, element):
        super().add(element)
        self.fifo_queue.append(element)

        if len(self) > self.max_size:
            last = self.fifo_queue.popleft()
            self.remove(last)


