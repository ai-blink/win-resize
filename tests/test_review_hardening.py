#!/usr/bin/env python3
"""Regression coverage for stability findings from the full code review."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT_DIR = Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QApplication

import final_build
import run_gui
import core.integrated_mouse_constraint as mouse_module
import core.window_state_manager as state_module
import gui.theme_manager as theme_module
from core.integrated_mouse_constraint import IntegratedMouseConstraint
from core.profile_manager import (
    MatchingCriteria,
    MatchingStrategy,
    Profile,
    ProfileManager,
    WindowConfiguration,
)
from core.window_state_manager import TransparencyEffect, WindowStateManager
from core.windows_api import WindowRect
from gui.main_window import WindowInfo, WindowResizerMainWindow
from gui.theme_manager import ColorScheme, ThemeElement, ThemeManager, ThemeType


class ProfilePersistenceRecoveryTest(unittest.TestCase):
    def make_profile(self):
        return Profile(
            name="Saved profile",
            window_config=WindowConfiguration(x=1, y=2, width=300, height=200),
            matching_criteria=MatchingCriteria(
                strategy=MatchingStrategy.EXACT_TITLE,
                window_title_pattern="Saved window",
            ),
        )

    def test_failed_save_preserves_primary_file_and_backup_recovers(self):
        with tempfile.TemporaryDirectory() as storage_path:
            manager = ProfileManager(storage_path)
            profile = self.make_profile()
            manager.profiles[profile.id] = profile
            self.assertTrue(manager.save_profiles())
            original_data = json.loads(manager.profiles_file.read_text(encoding="utf-8"))

            with patch("core.profile_manager.json.dump", side_effect=OSError("write failure")):
                self.assertFalse(manager.save_profiles())

            saved_data = json.loads(manager.profiles_file.read_text(encoding="utf-8"))
            self.assertEqual(saved_data, original_data)

            backup_file = manager.profiles_file.with_suffix(".json.backup")
            backup_file.write_text(json.dumps(original_data), encoding="utf-8")
            manager.profiles_file.write_text("{invalid json", encoding="utf-8")

            recovered_manager = ProfileManager(storage_path)
            self.assertIn(profile.id, recovered_manager.profiles)


class FakeTimerSignal:
    def __init__(self):
        self.callback = None

    def connect(self, callback):
        self.callback = callback


class FakeTimer:
    instances = []

    def __init__(self, *_args):
        self.timeout = FakeTimerSignal()
        self.stopped = False
        FakeTimer.instances.append(self)

    def start(self, _duration):
        pass

    def stop(self):
        self.stopped = True

    def fire(self):
        self.timeout.callback()


class WindowsControlRegressionTest(unittest.TestCase):
    def test_smooth_transparency_uses_math_helpers_and_stops_finished_timer(self):
        manager = WindowStateManager()
        manager.animation_enabled = True
        manager.animation_steps = 1
        manager._set_transparency_direct = lambda *_args: True
        FakeTimer.instances.clear()

        with patch.object(state_module, "QTimer", FakeTimer):
            self.assertTrue(
                manager._set_transparency_animated(
                    100,
                    0,
                    100,
                    TransparencyEffect.SMOOTH,
                )
            )
            timer = FakeTimer.instances[0]
            timer.fire()
            timer.fire()

        self.assertTrue(timer.stopped)
        self.assertNotIn(100, manager.transparency_timers)

    def test_removing_constraint_releases_clipcursor(self):
        captured_arguments = []
        controller = IntegratedMouseConstraint()
        controller._stop_polling_monitor = lambda: None
        fake_windll = SimpleNamespace(
            user32=SimpleNamespace(
                ClipCursor=lambda rect: captured_arguments.append(rect) or 1,
            )
        )

        with patch.object(mouse_module, "windll", fake_windll):
            self.assertTrue(controller.remove_constraint())

        self.assertEqual(captured_arguments, [None])


class ThemeAndFeedbackRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.original_palette = self.app.palette()
        self.original_stylesheet = self.app.styleSheet()

    def tearDown(self):
        self.app.setPalette(self.original_palette)
        self.app.setStyleSheet(self.original_stylesheet)

    def test_system_theme_uses_detected_theme_on_first_start(self):
        class MemorySettings:
            def value(self, key, default=None, **_kwargs):
                values = {
                    "theme": "system",
                    "color_scheme": "Light",
                    "follow_system": False,
                }
                return values.get(key, default)

            def setValue(self, *_args):
                pass

        with patch.object(theme_module, "QSettings", return_value=MemorySettings()), patch.object(
            ThemeManager,
            "_detect_system_theme",
            return_value="light",
        ):
            manager = ThemeManager()

        self.assertTrue(manager.follow_system)
        self.assertEqual(manager.current_theme, ThemeType.LIGHT)
        self.assertEqual(manager.current_scheme.name, "Light")

    def test_selected_text_contrasts_with_custom_selection_color(self):
        manager = ThemeManager()
        colors = {element: "#111111" for element in ThemeElement}
        colors[ThemeElement.TEXT] = "#eeeeee"
        colors[ThemeElement.SELECTION] = "#111111"
        manager.current_scheme = ColorScheme(name="Low contrast selection", colors=colors)
        manager._apply_theme_to_application()

        selected_text = self.app.palette().color(QPalette.HighlightedText)
        self.assertEqual(selected_text.name(), "#ffffff")

    def test_selected_profile_without_match_updates_status_text(self):
        window = WindowResizerMainWindow()
        profile = Profile(
            name="Missing target",
            window_config=WindowConfiguration(x=0, y=0, width=100, height=100),
            matching_criteria=MatchingCriteria(
                strategy=MatchingStrategy.EXACT_TITLE,
                window_title_pattern="Missing target",
            ),
        )
        window.get_selected_profile = lambda: profile
        window.window_list = [
            WindowInfo(
                hwnd=101,
                title="Other window",
                rect=WindowRect(0, 0, 300, 200),
                process_name="other.exe",
                pid=101,
                executable_path="",
            )
        ]
        window.status_label.setText("Ready")

        try:
            window.apply_selected_profile()
            self.assertIn("일치하는 창을 찾지 못했습니다", window.status_label.text())
        finally:
            window._quit_requested = True
            window.close()


class StartupAndBuildRegressionTest(unittest.TestCase):
    def test_high_dpi_configuration_is_static_and_pre_application(self):
        calls = []

        class FakeApplication:
            @staticmethod
            def setAttribute(attribute, value):
                calls.append((attribute, value))

        with patch.object(run_gui, "QApplication", FakeApplication):
            run_gui.configure_high_dpi()

        self.assertEqual(len(calls), 2)
        self.assertTrue(all(value for _attribute, value in calls))

    def test_existing_instance_is_rejected_and_its_mutex_handle_is_closed(self):
        class FakeKernel32:
            def __init__(self):
                self.created_names = []
                self.closed_handles = []

            def CreateMutexW(self, _attributes, _initial_owner, name):
                self.created_names.append(name)
                return 101

            def CloseHandle(self, handle):
                self.closed_handles.append(handle)
                return True

        kernel32 = FakeKernel32()
        guard = run_gui.SingleInstanceGuard(kernel32=kernel32)

        with patch.object(
            run_gui.ctypes,
            "get_last_error",
            return_value=run_gui.ERROR_ALREADY_EXISTS,
        ):
            self.assertFalse(guard.acquire())

        self.assertEqual(kernel32.created_names, [run_gui.MUTEX_NAME])
        self.assertEqual(kernel32.closed_handles, [101])

    def test_main_instance_releases_its_mutex_handle(self):
        class FakeKernel32:
            def __init__(self):
                self.closed_handles = []

            def CreateMutexW(self, _attributes, _initial_owner, _name):
                return 202

            def CloseHandle(self, handle):
                self.closed_handles.append(handle)
                return True

        kernel32 = FakeKernel32()
        guard = run_gui.SingleInstanceGuard(kernel32=kernel32)

        with patch.object(run_gui.ctypes, "get_last_error", return_value=0):
            self.assertTrue(guard.acquire())

        guard.release()

        self.assertEqual(kernel32.closed_handles, [202])

    def test_duplicate_launch_exits_before_opening_main_window(self):
        class FakeApplication:
            def __init__(self, _arguments):
                pass

            def setApplicationName(self, _name):
                pass

            def setApplicationVersion(self, _version):
                pass

            def setOrganizationName(self, _name):
                pass

            def setQuitOnLastWindowClosed(self, _enabled):
                pass

        guard = SimpleNamespace(acquire=lambda: False, release=lambda: None)

        with patch.object(run_gui, "setup_logging"), patch.object(
            run_gui,
            "configure_high_dpi",
        ), patch.object(run_gui, "QApplication", FakeApplication), patch.object(
            run_gui,
            "SingleInstanceGuard",
            return_value=guard,
        ), patch.object(run_gui.QMessageBox, "information") as information, patch.object(
            run_gui,
            "WindowResizerMainWindow",
        ) as main_window:
            self.assertEqual(run_gui.main(), 0)

        information.assert_called_once()
        main_window.assert_not_called()

    def test_build_command_does_not_require_generated_icon(self):
        with tempfile.TemporaryDirectory() as project_path:
            project_root = Path(project_path)
            main_script = project_root / "run_gui.py"
            main_script.write_text("", encoding="utf-8")

            command, icon_path = final_build.create_build_command(project_root, main_script)

        self.assertEqual(icon_path, project_root / "src" / "img" / "windowresizer.ico")
        self.assertIn("--paths=src", command)
        self.assertFalse(any(argument.startswith("--icon=") for argument in command))


if __name__ == "__main__":
    unittest.main()
