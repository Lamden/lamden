from unittest import TestCase


class TestExecutor(TestCase):

    """
    Tests that recv_multipart:
    - sets header to None if ignore_first_frame is True
    - must have exactly 2 frames if ignore_first_frame is False
    - first frame must be decode() able
    """
    def test_recv_multipart(self):
        pass