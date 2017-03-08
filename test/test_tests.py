import unittest


class GenericTest(unittest.TestCase):
    def test_if_tests_are_working(self):
        """This test should never fail"""
        self.assertTrue(True, "this should never happen.")
