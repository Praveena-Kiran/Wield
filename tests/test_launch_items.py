import os
import tempfile
import unittest
from unittest import mock

from backend.automation import launch_items as L

try:
    import PySide6  # noqa: F401
    HAVE_QT = True
except ImportError:  # CI's unit-test job installs only the standard library
    HAVE_QT = False


class ItemTests(unittest.TestCase):

    def test_make_item_and_labels(self):
        self.assertEqual(L.make_item("website", "https://www.github.com/me")["label"], "github.com")
        self.assertEqual(L.make_item("app", r"C:\Games\Steam\steam.exe")["label"], "steam")
        self.assertEqual(L.make_item("folder", "/home/me/projects/")["label"], "projects")
        self.assertEqual(L.make_item("app", "code", "VS Code")["label"], "VS Code")

    def test_bad_items(self):
        for kind, target in (("game", "x"), ("app", "  "), ("website", "two words")):
            with self.assertRaises(ValueError):
                L.make_item(kind, target)

    def test_clean_items_skips_broken_entries(self):
        items = L.clean_items([{"kind": "app", "target": "code"}, {"kind": "?"}, "junk", None])
        self.assertEqual([i["target"] for i in items], ["code"])

    def test_flow_steps_round_trip(self):
        items = [L.make_item("app", "code", "VS Code"), L.make_item("website", "github.com"),
                 L.make_item("folder", "/tmp", "Temp")]
        steps = L.to_flow_steps(items)
        self.assertEqual(steps[1], {"type": "website", "url": "github.com", "label": "github.com"})
        self.assertEqual(L.from_flow_steps(steps + [{"type": "wait", "duration": 2}]), items)

    def test_launch_all_reports_failures_and_carries_on(self):
        opened = []

        def fake(item, aliases):
            if item["target"] == "bad":
                raise L.LaunchError("not found")
            opened.append(item["target"])

        items = [L.make_item("app", "bad"), L.make_item("app", "good")]
        failures = L.launch_all(items, launch=fake)
        self.assertEqual(opened, ["good"])
        self.assertEqual(failures, ["bad: not found"])

    def test_missing_folder_is_a_friendly_error(self):
        with self.assertRaises(L.LaunchError):
            L.launch_item(L.make_item("folder", "/no/such/folder/here"))


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class StudioListTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = mock.patch.dict(os.environ, {"WIELD_DATA_DIR": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_coding_studio_list_persists(self):
        from frontend.pages.coding_page import CodingPage
        page = CodingPage()
        try:
            before = len(page.launch_list.items())
            self.assertGreater(before, 0)                 # VS Code, Terminal, GitHub
            page.launch_list.add_item(L.make_item("folder", "/tmp", "Projects"))
            page.launch_list.remove_item(0)
        finally:
            page.deleteLater()

        again = CodingPage()
        try:
            labels = [i["label"] for i in again.launch_list.items()]
            self.assertEqual(len(labels), before)
            self.assertIn("Projects", labels)
            self.assertNotIn("VS Code", labels)
        finally:
            again.deleteLater()

    def test_gaming_studio_list_persists(self):
        from frontend.pages.custom_page import CustomPage
        page = CustomPage()
        try:
            self.assertTrue(page.load_studio("Gaming Studio"))
            page.launch_list.add_item(L.make_item("website", "paper.io"))
            page.load_studio("Gaming Studio")
            labels = [i["label"] for i in page.launch_list.items()]
            self.assertIn("paper.io", labels)
            self.assertIn("Steam", labels)
        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
