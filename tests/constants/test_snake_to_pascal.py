from unittest import TestCase
from cilantro import snake_to_pascal


class TestSnake_to_pascal(TestCase):
    def test_basic_word_works(self):
        string = 'something'
        self.assertEqual(snake_to_pascal(string), 'Something')

    def test_multiple_words_works(self):
        string = 'something-else'
        self.assertEqual(snake_to_pascal(string), 'SomethingElse')

    def test_many_multiple_words_works(self):
        string = 'something-else-in-and-of-itself'
        self.assertEqual(snake_to_pascal(string), 'SomethingElseInAndOfItself')

    def test_other_than_hyphen_doesnt_work(self):
        string = 'something_else'
        self.assertEqual(snake_to_pascal(string), 'Something_Else')