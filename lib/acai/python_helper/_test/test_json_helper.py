import unittest

from acai.python_helper.json_helper import (
    dict_lower_all_keys,
    dict_lower_toplevel_keys,
    get_value_from_path,
)


class TestJsonHelperFunctions(unittest.TestCase):

    def test_dict_lower_all_keys(self):
        test_dict = {"A": 1, "B": {"C": 2, "D": {"E": 3}}}
        expected_dict = {"a": 1, "b": {"c": 2, "d": {"e": 3}}}
        self.assertEqual(dict_lower_all_keys(test_dict), expected_dict)

    def test_dict_lower_toplevel_keys(self):
        test_dict = {"A": 1, "B": {"C": 2, "D": 3}}
        expected_dict = {"a": 1, "b": {"C": 2, "D": 3}}
        self.assertEqual(dict_lower_toplevel_keys(test_dict), expected_dict)

    def test_get_value_from_path_exists(self):
        test_dict = {"a": {"b": {"c": 2}}}
        self.assertEqual(get_value_from_path(test_dict, "a.b.c"), 2)

    def test_get_value_from_path_not_exists(self):
        test_dict = {"a": {"b": {"c": 2}}}
        self.assertIsNone(get_value_from_path(test_dict, "a.b.d"))
        self.assertIsNone(get_value_from_path(test_dict, "d.e"))

    def test_get_value_from_path_non_dict_value(self):
        test_dict = {"a": {"b": "value"}}
        self.assertEqual(get_value_from_path(test_dict, "a.b"), "value")


if __name__ == "__main__":
    unittest.main()
