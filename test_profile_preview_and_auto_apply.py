#!/usr/bin/env python3
"""Focused tests for profile preview and automatic profile application."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtWidgets import QApplication

from core.profile_manager import (
    MatchingCriteria,
    MatchingStrategy,
    Profile,
    ProfileManager,
    WindowConfiguration,
)
from core.window_monitor import MonitoringConfig, WindowEvent, WindowMonitor
from gui.main_window import ProfilePreviewOverlay
from gui.profile_editor import ProfileEditorDialog
from gui.theme_manager import get_theme_manager


class RecordingProfileManager:
    def __init__(self):
        self.calls = []

    def apply_profile(self, profile_id, window_info):
        self.calls.append((profile_id, window_info))
        return True


class ListingProfileManager(RecordingProfileManager):
    def __init__(self, profiles):
        super().__init__()
        self.profiles = profiles

    def list_profiles(self):
        return self.profiles


class ProfilePreviewAndAutoApplyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_profile(self, strategy=MatchingStrategy.PROCESS_NAME):
        return Profile(
            name="Auto profile",
            window_config=WindowConfiguration(x=30, y=40, width=500, height=300),
            matching_criteria=MatchingCriteria(
                strategy=strategy,
                window_title_pattern="Target window",
                process_name_pattern="target.exe",
            ),
            auto_apply=True,
        )

    def test_auto_monitor_respects_profile_matching_strategy(self):
        profile = self.make_profile()
        monitor = WindowMonitor(RecordingProfileManager())
        wrong_process = SimpleNamespace(
            hwnd=101,
            title="Target window",
            process_name="other.exe",
            class_name="",
            rect=None,
            process_info=None,
        )
        matching_process = SimpleNamespace(
            hwnd=102,
            title="Unrelated title",
            process_name="target.exe",
            class_name="",
            rect=None,
            process_info=None,
        )

        self.assertFalse(monitor._profile_matches_window(profile, wrong_process))
        self.assertTrue(monitor._profile_matches_window(profile, matching_process))

    def test_auto_monitor_uses_full_profile_manager_apply_path(self):
        manager = RecordingProfileManager()
        monitor = WindowMonitor(manager, MonitoringConfig(max_retries=1))
        profile = self.make_profile()
        window = SimpleNamespace(
            hwnd=200,
            title="Target window",
            process_name="target.exe",
            class_name="WindowClass",
            rect=None,
            process_info=SimpleNamespace(
                name="target.exe",
                exe_path=r"C:\\Apps\\Target\\target.exe",
            ),
        )

        self.assertTrue(monitor._apply_profile_to_window(window, profile))
        self.assertEqual(len(manager.calls), 1)
        profile_id, window_info = manager.calls[0]
        self.assertEqual(profile_id, profile.id)
        self.assertEqual(window_info["process_name"], "target.exe")
        self.assertEqual(window_info["class_name"], "WindowClass")
        self.assertEqual(window_info["executable_path"], r"C:\\Apps\\Target\\target.exe")

    def test_executable_path_matching_survives_process_restart(self):
        criteria = MatchingCriteria(
            strategy=MatchingStrategy.EXECUTABLE_PATH,
            executable_path_pattern=r"C:\\Apps\\Target\\target.exe",
        )

        self.assertTrue(criteria.matches_window({
            "executable_path": r"C:\\Apps\\Target\\target.exe"
        }))
        self.assertFalse(criteria.matches_window({
            "executable_path": r"C:\\Apps\\Other\\target.exe"
        }))

    def test_new_profile_prefers_executable_path_when_available(self):
        with tempfile.TemporaryDirectory() as storage_path:
            manager = ProfileManager(storage_path)
            profile = manager.create_profile(
                "Path profile",
                window_info={
                    "title": "Target window",
                    "process_name": "target.exe",
                    "executable_path": r"C:\\Apps\\Target\\target.exe",
                },
            )

        self.assertEqual(
            profile.matching_criteria.strategy,
            MatchingStrategy.EXECUTABLE_PATH,
        )
        self.assertEqual(
            profile.matching_criteria.executable_path_pattern,
            r"C:\\Apps\\Target\\target.exe",
        )

    def test_auto_monitor_skips_matching_manual_profile(self):
        manual_profile = Profile(
            name="Manual profile",
            window_config=WindowConfiguration(x=1, y=1, width=100, height=100),
            matching_criteria=MatchingCriteria(
                strategy=MatchingStrategy.EXACT_TITLE,
                window_title_pattern="Target window",
            ),
            auto_apply=False,
        )
        auto_profile = self.make_profile()
        manager = ListingProfileManager([manual_profile, auto_profile])
        monitor = WindowMonitor(manager, MonitoringConfig(max_retries=1))
        applied_profiles = []
        monitor._apply_profile_to_window = lambda window, profile: applied_profiles.append(profile.id) or True
        window = SimpleNamespace(
            hwnd=300,
            title="Target window",
            process_name="target.exe",
            class_name="",
            rect=None,
            process_info=None,
        )

        monitor._apply_matching_profile(WindowEvent("created", window.hwnd, window))

        self.assertEqual(applied_profiles, [auto_profile.id])

    def test_preview_overlay_uses_saved_profile_geometry(self):
        profile = self.make_profile()
        overlay = ProfilePreviewOverlay(profile, get_theme_manager())
        geometry = overlay.geometry()
        self.assertEqual((geometry.x(), geometry.y()), (30, 40))
        self.assertEqual((geometry.width(), geometry.height()), (500, 300))
        overlay.close()

    def test_new_profile_auto_apply_is_opt_in(self):
        dialog = ProfileEditorDialog()
        try:
            self.assertFalse(dialog.auto_apply_check.isChecked())
            self.assertEqual(dialog.auto_apply_check.text(), "새 창 감지 시 자동 적용")
        finally:
            dialog.close()

    def test_executable_path_mode_exposes_only_path_controls(self):
        dialog = ProfileEditorDialog()
        try:
            path_index = dialog.matching_strategy_combo.findData("executable_path")
            dialog.matching_strategy_combo.setCurrentIndex(path_index)
            self.app.processEvents()

            self.assertFalse(dialog.window_title_edit.isEnabled())
            self.assertFalse(dialog.process_name_edit.isEnabled())
            self.assertTrue(dialog.executable_path_edit.isEnabled())
            self.assertIn("PID", dialog.matching_help_label.text())
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
