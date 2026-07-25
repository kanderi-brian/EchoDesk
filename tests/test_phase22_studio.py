import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    HAS_PYSIDE = True
except ModuleNotFoundError:
    QApplication = None
    HAS_PYSIDE = False


@unittest.skipUnless(HAS_PYSIDE, "PySide6 is required for Studio UI tests")
class Phase22StudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from brain.brain import EchoBrain
        from ui.studio import ChatWorkspace, Dashboard, SessionStore, StudioMainWindow
        globals().update(EchoBrain=EchoBrain, ChatWorkspace=ChatWorkspace, Dashboard=Dashboard,
                         SessionStore=SessionStore, StudioMainWindow=StudioMainWindow)
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.brain = EchoBrain()

    def test_dashboard_flattens_nested_summary(self):
        self.assertIn(("a.b", "2"), Dashboard._flatten({"a": {"b": 2}}))

    def test_chat_workspace_accepts_attachments(self):
        chat = ChatWorkspace(self.brain)
        chat.attach_file("example.txt")
        self.assertEqual(["example.txt"], chat.attachments)

    def test_session_store_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SessionStore(os.path.join(directory, "session.json")); store.save({"page": 2})
            self.assertEqual(2, store.load()["page"])

    def test_main_window_creates_all_dashboard_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            window = StudioMainWindow(self.brain, os.path.join(directory, "session.json"))
            self.assertEqual("EchoDesk Studio", window.windowTitle())
            self.assertGreaterEqual(window.navigation.count(), 10)
            self.assertIn("Performance", window.dashboards)
            window.close()

    def test_performance_dashboard_loads(self):
        dashboard = Dashboard("Performance", self.brain.get_performance_summary)
        dashboard.refresh()
        self.assertGreater(dashboard.table.rowCount(), 0)

    def test_session_restore_selects_saved_page(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "session.json"); SessionStore(path).save({"page": 3})
            window = StudioMainWindow(self.brain, path)
            self.assertEqual(3, window.navigation.currentRow()); window.close()


if __name__ == "__main__": unittest.main()
