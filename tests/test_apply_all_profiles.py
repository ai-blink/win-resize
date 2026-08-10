#!/usr/bin/env python3
"""Focused regression test for the manual Apply All action."""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtWidgets import QApplication

from core.windows_api import WindowRect
from gui.main_window import WindowInfo, WindowResizerMainWindow


class FakeWin32Gui:
    @staticmethod
    def IsWindow(hwnd):
        return True


class CapturingProfileManager:
    def __init__(self, expected_executable_path):
        self.expected_executable_path = expected_executable_path
        self.windows_info = []

    def apply_all_profiles(self, windows_info):
        self.windows_info = windows_info
        matched = [
            window
            for window in windows_info
            if window.get("executable_path") == self.expected_executable_path
        ]
        return {
            "applied": ["Path profile -> Target"] if matched else [],
            "failed": [],
        }


class ApplyAllProfilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindowResizerMainWindow()
        self.executable_path = r"C:\Apps\Target\target.exe"
        self.window.window_list = [
            WindowInfo(
                hwnd=101,
                title="Target",
                rect=WindowRect(10, 20, 410, 320),
                process_name="target.exe",
                pid=101,
                executable_path=self.executable_path,
            )
        ]
        self.profile_manager = CapturingProfileManager(self.executable_path)
        self.window.profile_manager = self.profile_manager

        def refresh_and_complete(on_complete=None):
            if on_complete:
                on_complete(self.window.window_list)

        self.window.refresh_window_list = refresh_and_complete

    def tearDown(self):
        self.window._quit_requested = True
        self.window.close()

    def test_apply_all_passes_executable_path_to_profile_matching(self):
        original_win32gui = sys.modules.get("win32gui")
        sys.modules["win32gui"] = FakeWin32Gui
        try:
            self.window.auto_apply_profiles()
        finally:
            if original_win32gui is None:
                del sys.modules["win32gui"]
            else:
                sys.modules["win32gui"] = original_win32gui

        self.assertEqual(
            self.profile_manager.windows_info[0]["executable_path"],
            self.executable_path,
        )
        self.assertEqual(self.window.status_label.text(), "1개 프로필 자동 적용됨")

    def test_apply_all_waits_for_the_refreshed_window_list(self):
        callbacks = []
        refreshed_window = self.window.window_list[0]
        self.window.window_list = []
        self.window.refresh_window_list = lambda on_complete=None: callbacks.append(on_complete)

        original_win32gui = sys.modules.get("win32gui")
        sys.modules["win32gui"] = FakeWin32Gui
        try:
            self.window.auto_apply_profiles()
            self.assertEqual(self.profile_manager.windows_info, [])

            self.assertEqual(len(callbacks), 1)
            callbacks[0]([refreshed_window])
        finally:
            if original_win32gui is None:
                del sys.modules["win32gui"]
            else:
                sys.modules["win32gui"] = original_win32gui

        self.assertEqual(self.profile_manager.windows_info, [
            {
                "hwnd": refreshed_window.hwnd,
                "title": refreshed_window.title,
                "process_name": refreshed_window.process_name,
                "pid": refreshed_window.pid,
                "executable_path": refreshed_window.executable_path,
                "rect": refreshed_window.rect,
                "is_maximized": refreshed_window.is_maximized,
                "is_minimized": refreshed_window.is_minimized,
                "is_visible": refreshed_window.is_visible,
            }
        ])


if __name__ == "__main__":
    unittest.main()
