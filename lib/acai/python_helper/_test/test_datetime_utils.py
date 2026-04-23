"""
ACAI Solutions
Copyright (C) 2025 ACAI GmbH
#
This file is part of ACAI SEMPER. Visit https://www.acai.gmbh or https://docs.acai.gmbh for more information.

Proprietary and Confidential - Licensed under ACAI Rahmen-Lizenzvertrag + Order Form (Subscription required)
For full license text, see LICENSE file in repository root.
#
For commercial licensing, contact: contact@acai.gmbh

"""

import unittest
from datetime import datetime

from acai.python_helper.datetime_utils import (
    aws_timestamp_to_datetime,
    aws_timestamp_to_yyyymmdd_hhmmss,
    datetime_to_yyyymmdd_hhmmss,
)


class TestDatetimeFunctions(unittest.TestCase):
    def test_datetime_to_yyyymmdd_hhmmss(self):
        dt = datetime(2022, 4, 9, 14, 53, 22)
        self.assertEqual(datetime_to_yyyymmdd_hhmmss(dt), "20220409_145322")

    def test_aws_timestamp_to_yyyymmdd_hhmmss(self):
        timestamp = "2019-12-20T11:47:26Z"
        self.assertEqual(aws_timestamp_to_yyyymmdd_hhmmss(timestamp), "20191220_114726")

    def test_aws_timestamp_to_datetime(self):
        timestamp = "2019-12-20T11:47:26Z"
        expected_dt = datetime(2019, 12, 20, 11, 47, 26)
        self.assertEqual(aws_timestamp_to_datetime(timestamp), expected_dt)
