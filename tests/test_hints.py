import unittest
from bot import services

class HintFormattingTest(unittest.TestCase):
    def test_format_hints_empty(self):
        self.assertEqual(services._format_hints([]), "")

    def test_format_hints_single(self):
        expected = "Предыдущие уточнения:\n1) hint1\n"
        self.assertEqual(services._format_hints(["hint1"]), expected)

    def test_format_hints_multiple(self):
        expected = "Предыдущие уточнения:\n1) one\n2) two\n"
        self.assertEqual(services._format_hints(["one", "two"]), expected)

if __name__ == '__main__':
    unittest.main()
