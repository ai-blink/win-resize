#!/usr/bin/env python3
"""Focused regression test for deleting a newly added profile."""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtWidgets import QApplication, QMessageBox

from core.profile_manager import (
    MatchingCriteria,
    MatchingStrategy,
    Profile,
    WindowConfiguration,
)
from core.windows_api import WindowRect
import gui.main_window as main_window_module
from gui.main_window import WindowInfo, WindowResizerMainWindow


class MemoryProfileManager:
    def __init__(self):
        self.profiles = {}
        self.deleted_ids = []

    def create_profile(self, name, description, window_info, window_config):
        profile = Profile(
            name=name,
            description=description,
            window_config=window_config,
            matching_criteria=MatchingCriteria(
                strategy=MatchingStrategy.PROCESS_NAME,
                process_name_pattern=window_info["process_name"],
            ),
        )
        self.profiles[profile.id] = profile
        return profile

    def list_profiles(self):
        return list(self.profiles.values())

    def delete_profile(self, profile_id):
        self.deleted_ids.append(profile_id)
        return self.profiles.pop(profile_id, None) is not None


class ConfirmDeleteMessageBox:
    Question = QMessageBox.Question
    Yes = QMessageBox.Yes
    No = QMessageBox.No

    def __init__(self, *args):
        pass

    def setIcon(self, *args):
        pass

    def setWindowTitle(self, *args):
        pass

    def setText(self, *args):
        pass

    def setStandardButtons(self, *args):
        pass

    def setDefaultButton(self, *args):
        pass

    def setStyleSheet(self, *args):
        pass

    def exec_(self):
        return self.Yes


class ProfileDeletionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindowResizerMainWindow()
        self.window.profile_manager = MemoryProfileManager()
        self.window.current_window = WindowInfo(
            hwnd=101,
            title="Delete target",
            rect=WindowRect(10, 20, 410, 320),
            process_name="delete-target.exe",
            pid=101,
            executable_path=r"C:\\Apps\\DeleteTarget\\delete-target.exe",
        )
        self.window.show_themed_input_dialog = lambda *args: ("Delete profile", True)
        self.window.show_themed_information = lambda *args: None

    def tearDown(self):
        self.window.close()

    def test_new_profile_is_selected_and_can_be_deleted(self):
        self.window.save_current_as_profile()
        profile = self.window.get_selected_profile()

        self.assertIsNotNone(profile)
        self.assertTrue(self.window.delete_profile_button.isEnabled())

        original_message_box = main_window_module.QMessageBox
        main_window_module.QMessageBox = ConfirmDeleteMessageBox
        try:
            self.window.delete_selected_profile()
        finally:
            main_window_module.QMessageBox = original_message_box

        self.assertEqual(self.window.profile_manager.deleted_ids, [profile.id])
        self.assertEqual(self.window.profile_table_widget.rowCount(), 0)


if __name__ == "__main__":
    unittest.main()
