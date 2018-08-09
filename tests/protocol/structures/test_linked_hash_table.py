from unittest import TestCase
from cilantro.protocol.structures.linked_hashtable import LinkedHashTable


class TestLinkedHashTable(TestCase):

    def test_empty_append(self):
        lht = LinkedHashTable()

        k, v = 'some key', b'a thicc value'
        lht.append(k, v)

        self.assertTrue(k in lht)
        self.assertEquals(lht.last.value, v)
        self.assertEquals(lht.first.value, v)

    def test_nonempty_append(self):
        lht = LinkedHashTable()

        k, v = 'some key', b'a thicc value'
        k2, v2 = 'another key', b'a thiccer value'
        k3, v3 = 'anotha one!', b'a thiccest value'
        k4, v4 = 'yet another one', b'a thiccerest value'
        lht.append(k, v)
        lht.append(k2, v2)
        lht.append(k3, v3)
        lht.append(k4, v4)

        for _k in (k, k2, k3):
            self.assertTrue(_k in lht)

        self.assertEquals(lht.first.value, v)
        self.assertEquals(lht.last.value, v4)
        self.assertEquals(lht.first.next.value, v2)
        self.assertEquals(lht.last.previous.value, v3)

    def test_pop_empty(self):
        lht = LinkedHashTable()
        self.assertEquals(None, lht.pop())

    def test_popleft_empty(self):
        lht = LinkedHashTable()
        self.assertEquals(None, lht.popleft())

    def test_pop(self):
        lht = LinkedHashTable()

        k, v = 'some key', b'a thicc value'
        k2, v2 = 'another key', b'a thiccer value'
        k3, v3 = 'anotha one!', b'a thiccest value'
        k4, v4 = 'yet another one', b'a thiccerest value'
        lht.append(k, v)
        lht.append(k2, v2)
        lht.append(k3, v3)
        lht.append(k4, v4)

        item = lht.pop()

        self.assertEquals(item, v4)
        self.assertEquals(lht.last.value, v3)
        self.assertEquals(lht.first.value, v)

    def test_popleft(self):
        lht = LinkedHashTable()

        k, v = 'some key', b'a thicc value'
        k2, v2 = 'another key', b'a thiccer value'
        k3, v3 = 'anotha one!', b'a thiccest value'
        k4, v4 = 'yet another one', b'a thiccerest value'
        lht.append(k, v)
        lht.append(k2, v2)
        lht.append(k3, v3)
        lht.append(k4, v4)

        item = lht.popleft()

        self.assertEquals(item, v)
        self.assertEquals(lht.first.value, v2)
        self.assertEquals(lht.last.value, v4)

    def test_remove_leftmost(self):
        lht = LinkedHashTable()

        k, v = 'some key', b'a thicc value'
        k2, v2 = 'another key', b'a thiccer value'
        k3, v3 = 'anotha one!', b'a thiccest value'
        k4, v4 = 'yet another one', b'a thiccerest value'
        lht.append(k, v)
        lht.append(k2, v2)
        lht.append(k3, v3)
        lht.append(k4, v4)

        item = lht.remove(k)

        self.assertEquals(item, v)
        self.assertEquals(lht.first.value, v2)
        self.assertEquals(lht.last.value, v4)

    def test_remove_rightmost(self):
        lht = LinkedHashTable()

        k, v = 'some key', b'a thicc value'
        k2, v2 = 'another key', b'a thiccer value'
        k3, v3 = 'anotha one!', b'a thiccest value'
        k4, v4 = 'yet another one', b'a thiccerest value'
        lht.append(k, v)
        lht.append(k2, v2)
        lht.append(k3, v3)
        lht.append(k4, v4)

        item = lht.remove(k4)

        self.assertEquals(item, v4)
        self.assertEquals(lht.last.value, v3)
        self.assertEquals(lht.first.value, v)

    def test_remove_inner(self):
        lht = LinkedHashTable()

        k, v = 'some key', b'a thicc value'
        k2, v2 = 'another key', b'a thiccer value'
        k3, v3 = 'anotha one!', b'a thiccest value'
        k4, v4 = 'yet another one', b'a thiccerest value'
        lht.append(k, v)
        lht.append(k2, v2)
        lht.append(k3, v3)
        lht.append(k4, v4)

        item = lht.remove(k2)

        self.assertEquals(item, v2)

        self.assertEquals(lht.last.value, v4)
        self.assertEquals(lht.first.value, v)

        self.assertEquals(lht.first.next.value, v3)
        self.assertEquals(lht.last.previous.value, v3)
        self.assertEquals(lht.last.previous.previous.value, v)

