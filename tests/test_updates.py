import unittest

from backend import updates


class FakeSettings:
    def __init__(self, **values):
        self.values = dict(values)

    def get_setting(self, key):
        return self.values.get(key)

    def set_setting(self, key, value):
        self.values[key] = value


def release(tag, url="https://example.com/r", body="Fixes"):
    return lambda _url: {"tag_name": tag, "html_url": url, "body": body}


def offline(_url):
    raise OSError("no internet")


class VersionTests(unittest.TestCase):

    def test_parse_and_compare(self):
        self.assertEqual(updates.parse_version("v1.2.0"), (1, 2, 0))
        self.assertEqual(updates.parse_version("1.2"), (1, 2, 0))
        self.assertIsNone(updates.parse_version("latest"))
        self.assertTrue(updates.is_newer("v1.10.0", "1.9.3"))
        self.assertFalse(updates.is_newer("1.1.0", "1.1.0"))
        self.assertFalse(updates.is_newer("garbage", "1.0.0"))

    def test_api_url_points_at_this_repo(self):
        self.assertEqual(
            updates.API_URL,
            "https://api.github.com/repos/Praveena-Kiran/Wield/releases/latest",
        )


class CheckTests(unittest.TestCase):

    def test_finds_a_newer_release(self):
        s = FakeSettings()
        found = updates.check(s, now=1e9, download=release("v99.0.0"))
        self.assertEqual(found["version"], "99.0.0")
        self.assertEqual(found["url"], "https://example.com/r")
        self.assertEqual(s.values["update_last_check"], 1e9)

    def test_same_or_older_version_is_not_an_update(self):
        self.assertIsNone(updates.check(FakeSettings(), now=1e9, download=release("v0.9.0")))

    def test_offline_is_quiet(self):
        self.assertIsNone(updates.check(FakeSettings(), now=1e9, download=offline))

    def test_every_few_hours(self):
        s = FakeSettings(update_last_check=1e9)
        self.assertIsNone(updates.check(s, now=1e9 + 3600, download=release("v99.0.0")))
        self.assertIsNotNone(updates.check(s, now=1e9 + 5 * 3600, download=release("v99.0.0")))

    def test_a_failed_check_does_not_count(self):
        # Offline at start-up: try again next time, not in a day.
        s = FakeSettings()
        self.assertIsNone(updates.check(s, now=1e9, download=offline))
        self.assertNotIn("update_last_check", s.values)
        self.assertIsNotNone(updates.check(s, now=1e9 + 60, download=release("v99.0.0")))

    def test_notify_once_per_version(self):
        s = FakeSettings()
        r = {"version": "99.0.0", "url": "u", "notes": ""}
        self.assertTrue(updates.should_notify(s, r))
        updates.mark_notified(s, r)
        self.assertFalse(updates.should_notify(s, r))
        self.assertTrue(updates.should_notify(s, dict(r, version="99.0.1")))
        self.assertFalse(updates.should_notify(s, None))

    def test_switched_off_and_skipped(self):
        off = FakeSettings(update_check=False)
        self.assertIsNone(updates.check(off, now=1e9, download=release("v99.0.0")))
        skipped = FakeSettings(update_skipped="99.0.0")
        self.assertIsNone(updates.check(skipped, now=1e9, download=release("v99.0.0")))
        # "Check now" ignores both.
        self.assertIsNotNone(updates.check(off, now=1e9, download=release("v99.0.0"), force=True))


if __name__ == "__main__":
    unittest.main()
