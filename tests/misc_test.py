import unittest

from utils.misc import repeat_on_fail


class MyTestCase(unittest.TestCase):
    def test_repeat_on_fail(self):
        counter = 7

        @repeat_on_fail()
        def say_hello():
            nonlocal counter
            if counter != 0:
                counter -= 1
                raise ArithmeticError("Error Message")
            return True

        res = say_hello()
        self.assertEqual(counter, 2)
        self.assertFalse(res)

        print()

        counter = 3
        res = say_hello()
        self.assertEqual(counter, 0)
        self.assertTrue(res)


if __name__ == '__main__':
    unittest.main()
