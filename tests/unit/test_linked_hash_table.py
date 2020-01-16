from unittest import TestCase
from cilantro_ee.containers.linked_hashtable import LinkedHashTable


class TestLinkedHashTable(TestCase):

    def test_empty_append(self):
        lht = LinkedHashTable()

        k, v = 'some key', b'a thicc value'
        lht.append(k, v)

        self.assertTrue(k in lht)
        self.assertEquals(lht._last.value, v)
        self.assertEquals(lht._first.value, v)
        self.assertEquals(len(lht), 1)

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

        self.assertEquals(lht._first.value, v)
        self.assertEquals(lht._last.value, v4)
        self.assertEquals(lht._first.next.value, v2)
        self.assertEquals(lht._last.previous.value, v3)
        self.assertEquals(len(lht), 4)

    def test_clear(self):
        lht = LinkedHashTable()

        k, v = 'some key', b'a thicc value'
        k2, v2 = 'another key', b'a thiccer value'
        k3, v3 = 'anotha one!', b'a thiccest value'
        k4, v4 = 'yet another one', b'a thiccerest value'
        lht.append(k, v)
        lht.append(k2, v2)
        lht.append(k3, v3)
        lht.append(k4, v4)

        lht.clear()

        self.assertEquals(len(lht), 0)
        self.assertEquals(lht._last, None)
        self.assertEquals(lht._first, None)

    def test_pop_empty(self):
        lht = LinkedHashTable()
        self.assertEquals(None, lht.pop_back())

    def test_popleft_empty(self):
        lht = LinkedHashTable()
        self.assertEquals(None, lht.pop_front()[1])

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

        item = lht.pop_back()

        self.assertEquals(item[1], v4)
        self.assertEquals(lht._last.value, v3)
        self.assertEquals(lht._first.value, v)
        self.assertEquals(len(lht), 3)

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

        item = lht.pop_front()

        self.assertEquals(item[1], v)
        self.assertEquals(lht._first.value, v2)
        self.assertEquals(lht._last.value, v4)
        self.assertEquals(len(lht), 3)

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

        self.assertEquals(item[1], v)
        self.assertEquals(lht._first.value, v2)
        self.assertEquals(lht._last.value, v4)
        self.assertEquals(len(lht), 3)

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

        self.assertEquals(item[1], v4)
        self.assertEquals(lht._last.value, v3)
        self.assertEquals(lht._first.value, v)
        self.assertEquals(len(lht), 3)

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

        self.assertEquals(lht._last.value, v4)
        self.assertEquals(lht._first.value, v)

        self.assertEquals(lht._first.next.value, v3)
        self.assertEquals(lht._last.previous.value, v3)
        self.assertEquals(lht._last.previous.previous.value, v)
        self.assertEquals(len(lht), 3)

