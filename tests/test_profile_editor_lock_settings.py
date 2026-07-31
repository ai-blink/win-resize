#!/usr/bin/env python3
"""Profile editor tests for the window position lock setting and theme styling."""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtWidgets import QApplication

from core.profile_manager import (
    MatchingCriteria,
    MatchingStrategy,
    Profile,
    WindowConfiguration,
)
from gui import profile_editor
from gui.profile_editor import ProfileEditorDialog
from gui.theme_manager import ThemeElement, ThemeManager, ThemeType, get_theme_manager


class ProfileEditorLockSettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.profile = Profile(
            name="Lock setting test",
            window_config=WindowConfiguration(x=10, y=20, width=800, height=600),
            matching_criteria=MatchingCriteria(
                strategy=MatchingStrategy.TITLE_CONTAINS,
                window_title_pattern="Test Window",
            ),
            lock_position=True,
        )

    def test_position_lock_loads_and_saves(self):
        dialog = ProfileEditorDialog(profile=self.profile)
        self.assertTrue(dialog.lock_position_check.isChecked())

        dialog.lock_position_check.setChecked(False)
        saved_data = []
        dialog.profile_saved.connect(saved_data.append)
        dialog._apply_saved_profile = lambda _data: {
            "matched_count": 0,
            "applied_count": 0,
            "matched_windows": [],
        }

        original_information = profile_editor.show_themed_information
        try:
            profile_editor.show_themed_information = lambda *args: None
            dialog.save_profile()
        finally:
            profile_editor.show_themed_information = original_information

        self.assertEqual(len(saved_data), 1)
        self.assertFalse(saved_data[0]["lock_position"])

    def test_profile_editor_uses_current_theme_colors(self):
        theme_manager = get_theme_manager()
        previous_theme = theme_manager.current_theme
        previous_scheme = theme_manager.current_scheme.name
        dialog = ProfileEditorDialog(profile=self.profile)

        try:
            for theme_type, scheme_name in (
                (ThemeType.DARK, "Dark"),
                (ThemeType.LIGHT, "Light"),
            ):
                self.assertTrue(theme_manager.set_theme(theme_type, scheme_name))
                dialog.apply_theme_styling()
                stylesheet = dialog.styleSheet()
                self.assertIn(
                    theme_manager.get_color_string(ThemeElement.BACKGROUND),
                    stylesheet,
                )
                self.assertIn(
                    theme_manager.get_color_string(ThemeElement.TEXT),
                    stylesheet,
                )
        finally:
            theme_manager.set_theme(previous_theme, previous_scheme)
            dialog.close()

    def test_initial_theme_applies_message_box_colors_globally(self):
        theme_manager = ThemeManager()
        stylesheet = self.app.styleSheet()

        self.assertIn("QMessageBox QLabel", stylesheet)
        self.assertIn(
            theme_manager.get_color_string(ThemeElement.TEXT),
            stylesheet,
        )


if __name__ == "__main__":
    unittest.main()
