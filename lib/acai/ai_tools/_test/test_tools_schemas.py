import unittest
from datetime import datetime

from acai.ai_tools.tools_schemas import (
    add_duration_to_datetime,
    get_current_datetime,
    set_reminder,
)


class TestAddDurationToDatetime(unittest.TestCase):
    def test_add_days(self):
        result = add_duration_to_datetime("2025-01-01", duration=10, unit="days")
        self.assertIn("January 11, 2025", result)

    def test_add_zero_days(self):
        result = add_duration_to_datetime("2025-06-15", duration=0, unit="days")
        self.assertIn("June 15, 2025", result)

    def test_add_weeks(self):
        result = add_duration_to_datetime("2025-01-01", duration=2, unit="weeks")
        self.assertIn("January 15, 2025", result)

    def test_add_hours(self):
        result = add_duration_to_datetime(
            "2025-01-01 10:00:00",
            duration=5,
            unit="hours",
            input_format="%Y-%m-%d %H:%M:%S",
        )
        self.assertIn("03:00:00 PM", result)

    def test_add_minutes(self):
        result = add_duration_to_datetime(
            "2025-01-01 10:00:00",
            duration=90,
            unit="minutes",
            input_format="%Y-%m-%d %H:%M:%S",
        )
        self.assertIn("11:30:00 AM", result)

    def test_add_seconds(self):
        result = add_duration_to_datetime(
            "2025-01-01 10:00:00",
            duration=3600,
            unit="seconds",
            input_format="%Y-%m-%d %H:%M:%S",
        )
        self.assertIn("11:00:00 AM", result)

    def test_add_months(self):
        result = add_duration_to_datetime("2025-01-15", duration=2, unit="months")
        self.assertIn("March 15, 2025", result)

    def test_add_months_wraps_year(self):
        result = add_duration_to_datetime("2025-11-15", duration=3, unit="months")
        self.assertIn("February 15, 2026", result)

    def test_add_months_clamps_day(self):
        # Jan 31 + 1 month -> Feb 28 (non-leap) or 29 (leap)
        result = add_duration_to_datetime("2025-01-31", duration=1, unit="months")
        self.assertIn("February 28, 2025", result)

    def test_add_months_leap_year(self):
        result = add_duration_to_datetime("2024-01-31", duration=1, unit="months")
        self.assertIn("February 29, 2024", result)

    def test_add_years(self):
        result = add_duration_to_datetime("2025-06-15", duration=3, unit="years")
        self.assertIn("June 15, 2028", result)

    def test_negative_duration(self):
        result = add_duration_to_datetime("2025-01-15", duration=-10, unit="days")
        self.assertIn("January 05, 2025", result)

    def test_unsupported_unit_raises(self):
        with self.assertRaises(ValueError):
            add_duration_to_datetime("2025-01-01", duration=1, unit="decades")

    def test_invalid_date_format_raises(self):
        with self.assertRaises(ValueError):
            add_duration_to_datetime("not-a-date", duration=1, unit="days")


class TestGetCurrentDatetime(unittest.TestCase):
    def test_default_format(self):
        result = get_current_datetime()
        # Should be parseable with the default format
        datetime.strptime(result, "%Y-%m-%d %H:%M:%S")

    def test_custom_format(self):
        result = get_current_datetime("%Y")
        self.assertEqual(len(result), 4)
        int(result)  # Should be a valid year

    def test_empty_format_raises(self):
        with self.assertRaises(ValueError):
            get_current_datetime("")


class TestSetReminder(unittest.TestCase):
    def test_set_reminder_prints(self):
        # set_reminder just prints; verify no exception
        set_reminder("test reminder", "2025-01-01T10:00:00")


if __name__ == "__main__":
    unittest.main()
