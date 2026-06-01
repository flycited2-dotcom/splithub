#!/usr/bin/env python3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AdminNotificationsUiTest(unittest.TestCase):
    def test_notifications_tab_and_actions_are_present(self):
        html = (ROOT / "admin.html").read_text(encoding="utf-8")

        self.assertIn("switchTab('notifications')", html)
        self.assertIn('id="pane-notifications"', html)
        self.assertIn("function sendPromotionPush()", html)
        self.assertIn("function sendManagerPush()", html)
        self.assertIn("function loadPushLog()", html)
        self.assertIn("if(name==='notifications')loadPushLog();", html)


if __name__ == "__main__":
    unittest.main()
