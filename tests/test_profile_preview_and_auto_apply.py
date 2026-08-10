#!/usr/bin/env python3
"""Focused tests for profile preview and automatic profile application."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtWidgets import QApplication

from core.profile_manager import (
    MatchingCriteria,
    MatchingStrategy,
    Profile,
    ProfileManager,
    WindowConfiguration,
)
from core.windows_api import WindowRect
from core.window_monitor import MonitoringConfig, WindowEvent, WindowMonitor
from gui.main_window import ProfilePreviewOverlay, WindowInfo, WindowResizerMainWindow
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


class RecordingWindowMonitor:
    def __init__(self, is_running=False):
        self.is_running = is_running
        self.start_calls = 0
        self.stop_calls = 0

    def get_statistics(self):
        return {"is_running": self.is_running}

    def start(self):
        self.start_calls += 1
        self.is_running = True
        return True

    def stop(self):
        self.stop_calls += 1
        self.is_running = False
        return True


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

    def test_enabled_realtime_profile_starts_new_window_monitor(self):
        monitor = RecordingWindowMonitor()
        window = SimpleNamespace(
            profile_manager=ListingProfileManager([self.make_profile()]),
            window_monitor=monitor,
        )

        self.assertTrue(WindowResizerMainWindow._sync_auto_apply_monitor(window))
        self.assertEqual(monitor.start_calls, 1)

    def test_disabled_realtime_profile_does_not_start_new_window_monitor(self):
        profile = self.make_profile()
        profile.auto_apply = False
        monitor = RecordingWindowMonitor()
        window = SimpleNamespace(
            profile_manager=ListingProfileManager([profile]),
            window_monitor=monitor,
        )

        self.assertTrue(WindowResizerMainWindow._sync_auto_apply_monitor(window))
        self.assertEqual(monitor.start_calls, 0)

    def test_auto_apply_profile_starts_realtime_geometry_monitor(self):
        profile = self.make_profile()
        monitoring_calls = []

        class RecordingManipulator:
            def enhanced_move_window(self, *_args):
                return SimpleNamespace(success=True)

        profile._set_always_on_top = lambda *_args: True
        profile._apply_advanced_features = lambda _hwnd: True
        profile._start_auto_monitoring = (
            lambda hwnd, window_info: monitoring_calls.append((hwnd, window_info)) or True
        )
        fake_win32gui = SimpleNamespace(
            IsWindow=lambda _hwnd: True,
            GetWindowPlacement=lambda _hwnd: (0, 1, None, None, None),
        )
        fake_win32con = SimpleNamespace(SW_SHOWMAXIMIZED=3)
        window_info = {"hwnd": 101, "title": "Target window"}

        with patch.dict(sys.modules, {
            "win32gui": fake_win32gui,
            "win32con": fake_win32con,
        }), patch(
            "core.enhanced_window_manipulator.EnhancedWindowManipulator",
            return_value=RecordingManipulator(),
        ):
            self.assertTrue(profile.apply_to_window(window_info))

        self.assertEqual(monitoring_calls, [(101, window_info)])

    def test_maximized_target_is_restored_before_normal_geometry_is_applied(self):
        profile = Profile(
            name="Restore geometry",
            window_config=WindowConfiguration(x=30, y=40, width=500, height=300),
            matching_criteria=MatchingCriteria(
                strategy=MatchingStrategy.EXACT_TITLE,
                window_title_pattern="Target window",
            ),
        )
        operations = []

        class RecordingManipulator:
            def enhanced_restore_window(self, hwnd):
                operations.append(("restore", hwnd))
                return SimpleNamespace(success=True)

            def enhanced_move_window(self, hwnd, x, y, width, height):
                operations.append(("move", hwnd, x, y, width, height))
                return SimpleNamespace(success=True)

        profile._set_always_on_top = lambda *_args: True
        profile._apply_advanced_features = lambda _hwnd: True
        profile._stop_auto_monitoring = lambda _hwnd: True
        fake_win32gui = SimpleNamespace(
            IsWindow=lambda _hwnd: True,
            GetWindowPlacement=lambda _hwnd: (0, 3, None, None, None),
        )
        fake_win32con = SimpleNamespace(SW_SHOWMAXIMIZED=3)

        with patch.dict(sys.modules, {
            "win32gui": fake_win32gui,
            "win32con": fake_win32con,
        }), patch(
            "core.enhanced_window_manipulator.EnhancedWindowManipulator",
            return_value=RecordingManipulator(),
        ):
            self.assertTrue(profile.apply_to_window({"hwnd": 101, "title": "Target window"}))

        self.assertEqual(
            operations,
            [
                ("restore", 101),
                ("move", 101, 30, 40, 500, 300),
            ],
        )

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
            self.assertEqual(
                dialog.auto_apply_check.text(),
                "새 창 감지 및 실시간 위치/크기 유지",
            )
        finally:
            dialog.close()

    def test_new_profile_editor_prefills_selected_window(self):
        dialog = ProfileEditorDialog(
            window_info={
                "title": "Target window",
                "process_name": "target.exe",
                "executable_path": r"C:\Apps\Target\target.exe",
                "rect": WindowRect(10, 20, 810, 620),
            }
        )
        try:
            self.assertEqual(dialog.name_edit.text(), "Target window 프로필")
            self.assertEqual(dialog.window_title_edit.text(), "Target window")
            self.assertEqual(dialog.process_name_edit.text(), "target.exe")
            self.assertEqual(dialog.executable_path_edit.text(), r"C:\Apps\Target\target.exe")
            self.assertEqual(
                (dialog.x_spin.value(), dialog.y_spin.value(),
                 dialog.width_spin.value(), dialog.height_spin.value()),
                (10, 20, 800, 600),
            )
            self.assertEqual(dialog.matching_strategy_combo.currentData(), "executable_path")
            self.assertGreaterEqual(
                dialog.window_settings_content.minimumHeight(),
                dialog.window_settings_content.sizeHint().height(),
            )
        finally:
            dialog.close()

    def test_prefilled_editor_payload_creates_profile(self):
        with tempfile.TemporaryDirectory() as storage_path:
            window = WindowResizerMainWindow()
            window.profile_manager = ProfileManager(storage_path)
            try:
                created_profile = window.on_profile_created({
                    "name": "Target window 프로필",
                    "description": "선택한 창에서 생성됨: Target window",
                    "auto_apply": False,
                    "enabled": True,
                    "window_config": {
                        "x": 10,
                        "y": 20,
                        "width": 800,
                        "height": 600,
                    },
                    "matching_criteria": {
                        "strategy": "executable_path",
                        "window_title_pattern": "Target window",
                        "process_name_pattern": "target.exe",
                        "executable_path_pattern": r"C:\Apps\Target\target.exe",
                        "case_sensitive": False,
                        "priority": 50,
                    },
                })

                self.assertIsNotNone(created_profile)
                profile = window.profile_manager.list_profiles()[0]
                self.assertEqual(profile.window_config.to_rect(), WindowRect(10, 20, 810, 620))
                self.assertEqual(
                    profile.matching_criteria.executable_path_pattern,
                    r"C:\Apps\Target\target.exe",
                )
            finally:
                window._quit_requested = True
                window.close()

    def test_selected_window_profile_keeps_current_coordinate_inputs(self):
        window = WindowResizerMainWindow()
        try:
            window.current_window = WindowInfo(
                hwnd=42,
                title="Target window",
                rect=WindowRect(10, 20, 810, 620),
                process_name="target.exe",
                executable_path=r"C:\\Apps\\Target\\target.exe",
            )
            window.x_spinbox.setValue(100)
            window.y_spinbox.setValue(200)
            window.width_spinbox.setValue(1200)
            window.height_spinbox.setValue(700)

            rect = window.current_profile_rect()

            self.assertEqual(rect, WindowRect(100, 200, 1300, 900))
        finally:
            window._quit_requested = True
            window.close()

    def test_failed_new_profile_handler_keeps_editor_open(self):
        saved_payloads = []
        dialog = ProfileEditorDialog(
            window_info={
                "title": "Target window",
                "process_name": "target.exe",
                "executable_path": r"C:\\Apps\\Target\\target.exe",
                "rect": WindowRect(10, 20, 810, 620),
            },
            save_handler=lambda _profile_data: None,
        )
        dialog.profile_saved.connect(saved_payloads.append)
        try:
            dialog.save_profile()

            self.assertEqual(saved_payloads, [])
            self.assertEqual(dialog.result(), 0)
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
