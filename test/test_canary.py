import unittest


class CanaryTest(unittest.TestCase):
    def test_canary(self):
        """This test should never fail."""
        self.assertTrue(True, "this should never happen.")
        self.assertRaises(ZeroDivisionError, (lambda: 1 / 0))
