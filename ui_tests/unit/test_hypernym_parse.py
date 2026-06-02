"""Unit tests for hypernym_identify output parsing."""
import unittest

from utils.conversion import parse_hypernym_list


class HypernymParseTest(unittest.TestCase):
    def test_ignores_format_hint_type(self):
        self.assertEqual(parse_hypernym_list("type"), [])
        self.assertEqual(parse_hypernym_list("text,type,mesh"), [])

    def test_arrow_lines(self):
        rows = parse_hypernym_list("Aspirin→Drug\n")
        self.assertEqual(rows, [{"entity": "Aspirin", "hypernym": "Drug"}])

    def test_json_array(self):
        raw = '[{"entity": "Aspirin", "hypernym": "Drug"}]'
        self.assertEqual(parse_hypernym_list(raw), [{"entity": "Aspirin", "hypernym": "Drug"}])


if __name__ == "__main__":
    unittest.main()
