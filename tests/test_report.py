"""Problems are reported by email, filled in with what helps."""

import unittest
from urllib.parse import parse_qs, unquote, urlparse

from backend import report
from backend.app_info import VERSION


class ReportTests(unittest.TestCase):

    def test_email_goes_to_the_maker_with_the_version(self):
        url = report.mailto_url()
        self.assertTrue(url.startswith("mailto:hipraveenakiran@gmail.com?"))
        query = parse_qs(urlparse(url).query)
        self.assertIn(VERSION, query["subject"][0])
        self.assertIn(VERSION, query["body"][0])
        self.assertIn("wield.log", query["body"][0])
        self.assertNotIn("Error:", query["body"][0])

    def test_a_crash_puts_the_error_in_short(self):
        error = "TypeError: drawLine(NoneType, NoneType) " + "x" * 2000
        body = unquote(report.mailto_url(error).split("&body=", 1)[1])
        self.assertIn("TypeError: drawLine", body)
        self.assertLess(len(body), 1200)
        self.assertIn("problem", report.subject(error))

    def test_spaces_and_lines_are_encoded(self):
        url = report.mailto_url("a & b\\nc")
        self.assertNotIn(" ", url)
        self.assertNotIn("\\n", url)


if __name__ == "__main__":
    unittest.main()
