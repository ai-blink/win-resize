#!/usr/bin/env python3
"""Focused regression test for profile action bar text clearance."""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtWidgets import QApplication

from gui.main_window import WindowResizerMainWindow
from gui.ui_scale_manager import DEFAULT_UI_SCALE_PERCENT, get_ui_scale_manager


class ProfileButtonBarLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ui_scale_manager = get_ui_scale_manager()
        self.original_scale = self.ui_scale_manager.scale_percent
        self.ui_scale_manager.set_scale(DEFAULT_UI_SCALE_PERCENT, persist=False)
        self.window = WindowResizerMainWindow()

    def tearDown(self):
        self.window.close()
        self.ui_scale_manager.set_scale(self.original_scale, persist=False)

    def test_profile_actions_have_text_clearance(self):
        controls = [
            self.window.edit_profile_button,
            self.window.delete_profile_button,
            self.window.apply_profile_button,
            self.window.apply_all_profiles_button,
            self.window.profile_preview_button,
            self.window.auto_apply_monitor_button,
            self.window.auto_apply_monitor_status_label,
            self.window.profile_count_label,
        ]

        self.assertEqual(self.window.profile_button_bar.height(), 41)
        for control in controls:
            self.assertEqual(control.height(), 31)
            self.assertGreaterEqual(
                control.height(),
                control.fontMetrics().height() + 12,
            )


if __name__ == "__main__":
    unittest.main()
