import unittest


class Test(unittest.TestCase):
    def test_example(self):
        self.assertEqual(1, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
