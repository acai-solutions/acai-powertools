import unittest

from acai.python_helper.utils import get_16_bytes_hash


class TestUtilsFunctions(unittest.TestCase):
    def test_get_16_bytes_hash(self):
        input_string = "test_string"
        expected_hash = "e3c529a07ccbe674"
        self.assertEqual(get_16_bytes_hash(input_string), expected_hash)
