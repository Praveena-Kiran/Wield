import os
import tempfile
import unittest
from unittest import mock

try:
    import PySide6  # noqa: F401
    HAVE_QT = True
except ImportError:  # CI's unit-test job installs only the standard library
    HAVE_QT = False


class CatalogTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = mock.patch.dict(os.environ, {"WIELD_DATA_DIR": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)
        from backend.studios import catalog
        self.catalog = catalog

    def titles(self):
        return [s["title"] for s in self.catalog.user_studios()]

    def test_core_studios_can_never_be_removed(self):
        for title in self.catalog.CORE:
            self.assertFalse(self.catalog.removable(title))
            self.assertFalse(self.catalog.remove(title))
            self.assertIn(title, self.titles())

    def test_optional_studios_can_be_removed_and_brought_back(self):
        c = self.catalog
        before = self.titles()
        self.assertTrue(c.is_optional("Coding Studio"))
        self.assertTrue(c.is_optional("Gaming Studio"))
        self.assertTrue(c.remove("Coding Studio"))
        self.assertTrue(c.remove("Gaming Studio"))
        self.assertNotIn("Coding Studio", self.titles())
        self.assertEqual(c.missing_optional(), ["Coding Studio", "Gaming Studio"])

        self.assertEqual(c.restore_optional(), ["Coding Studio", "Gaming Studio"])
        self.assertEqual(self.titles(), before)            # same places as before
        self.assertEqual(c.missing_optional(), [])
        self.assertEqual(c.restore_optional(), [])

    def test_your_own_studios_are_removable_but_not_restorable(self):
        import json
        from backend.paths import user_config_path
        studios = self.catalog.user_studios() + [{"title": "Study Studio", "type": "custom"}]
        with open(user_config_path("studios.json"), "w", encoding="utf-8") as f:
            json.dump(studios, f)
        self.assertFalse(self.catalog.is_optional("Study Studio"))
        self.assertTrue(self.catalog.remove("Study Studio"))
        self.assertEqual(self.catalog.missing_optional(), [])


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class HomeRemoveTests(unittest.TestCase):

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
        from frontend.pages.home import HomePage
        self.home = HomePage()
        self.home.refresh_studios()

    def tearDown(self):
        self.home.deleteLater()

    def remove_buttons(self):
        from PySide6.QtWidgets import QPushButton
        return {b.accessibleName() for b in self.home.findChildren(QPushButton)
                if b.accessibleName().startswith("Remove ")}

    def test_only_non_core_studios_have_a_remove_button(self):
        names = self.remove_buttons()
        self.assertIn("Remove Coding Studio", names)
        self.assertIn("Remove Gaming Studio", names)
        for core in ("Presentation Studio", "Browse & Media Studio", "Gesture Studio"):
            self.assertNotIn(f"Remove {core}", names)

    def test_rows_open_studios_without_an_open_button(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QFrame, QPushButton
        texts = {b.text() for b in self.home.findChildren(QPushButton)}
        self.assertNotIn("Open", texts)
        self.assertNotIn("Edit", texts)

        opened = []
        self.home.studio_selected.connect(opened.append)
        rows = {r.accessibleName(): r for r in self.home.findChildren(QFrame, "StudioRow")}
        QTest.mouseClick(rows["Open Presentation Studio"], Qt.LeftButton)
        QTest.keyClick(rows["Open Gesture Studio"], Qt.Key_Return)
        self.assertEqual(opened, ["Presentation Studio", "Gesture Studio"])

    def test_remove_from_home(self):
        removed = []
        self.home.studio_removed.connect(removed.append)
        self.assertTrue(self.home.remove_studio("Coding Studio", confirm=False))
        self.assertEqual(removed, ["Coding Studio"])
        self.assertFalse(self.home.remove_studio("Presentation Studio", confirm=False))
        titles = [s["title"] for s in self.home.load_studios()]
        self.assertNotIn("Coding Studio", titles)
        self.assertIn("Presentation Studio", titles)


if __name__ == "__main__":
    unittest.main()
