from datetime import date

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core.performance import bounded_date_range


class Phase61PerformanceTests(SimpleTestCase):
    def test_default_report_range_is_bounded(self):
        start, end = bounded_date_range({}, default_end=date(2026, 1, 31))
        self.assertEqual(end, date(2026, 1, 31))
        self.assertEqual((end - start).days + 1, 31)

    def test_report_range_rejects_more_than_maximum(self):
        with self.assertRaises(ValidationError):
            bounded_date_range({"start_date": "2020-01-01", "end_date": "2026-01-01"})

    def test_report_range_rejects_reversed_dates(self):
        with self.assertRaises(ValidationError):
            bounded_date_range({"start_date": "2026-02-01", "end_date": "2026-01-01"})

    def test_report_range_rejects_invalid_dates(self):
        with self.assertRaises(ValidationError):
            bounded_date_range({"start_date": "not-a-date"})
