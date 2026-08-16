#!/usr/bin/env python3
"""Regression coverage for profile shortcut persistence and registration."""

import os
import sys
import unittest
import ctypes
from ctypes import wintypes
from pathlib import Path
from unittest.mock import patch

import win32con

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtWidgets import QApplication

from core.hotkey_manager import (
    HotkeyAction,
    HotkeyDefinition,
    HotkeyManager,
    ModifierKeys,
    parse_hotkey_combination,
)
from core.profile_manager import (
    MatchingCriteria,
    MatchingStrategy,
    Profile,
    WindowConfiguration,
)
from gui import profile_editor
from gui.main_window import WindowResizerMainWindow
from gui.profile_editor import ProfileEditorDialog


class FakeProfileHotkeyManager:
    def __init__(self):
        self.hotkeys = {}
        self.cleared = False
        self.registered = []

    def clear_hotkeys(self):
        self.cleared = True
        self.hotkeys.clear()

    def add_hotkey(self, hotkey):
        self.hotkeys[hotkey.id] = hotkey
        return True

    def register_hotkey(self, hotkey_id):
        self.registered.append(hotkey_id)
        return True


class FakeProfileManager:
    def __init__(self, profiles):
        self.profiles = profiles

    def list_profiles(self):
        return self.profiles


class ProfileHotkeyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.profile = Profile(
            name="Shortcut profile",
            window_config=WindowConfiguration(x=10, y=20, width=800, height=600),
            matching_criteria=MatchingCriteria(
                strategy=MatchingStrategy.TITLE_CONTAINS,
                window_title_pattern="Target Window",
            ),
        )

    def test_editor_persists_all_enabled_hotkey_sets(self):
        dialog = ProfileEditorDialog(profile=self.profile)
        dialog.hotkey_enabled_check.setChecked(True)
        dialog.hotkey_sets[0]["enabled"].setChecked(True)
        dialog.hotkey_sets[0]["keys"].set_hotkey_string("Ctrl + Alt + E")
        dialog.hotkey_sets[1]["enabled"].setChecked(True)
        dialog.hotkey_sets[1]["keys"].set_hotkey_string("Ctrl + Shift + F")
        dialog.hotkey_sets[1]["action"].setCurrentIndex(2)

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
        self.assertEqual(
            saved_data[0]["hotkey_sets"],
            [
                {
                    "enabled": True,
                    "combination": "Ctrl + Alt + E",
                    "action": "apply_profile",
                },
                {
                    "enabled": True,
                    "combination": "Ctrl + Shift + F",
                    "action": "always_on_top_toggle",
                },
            ],
        )
        self.assertEqual(saved_data[0]["hotkey_combination"], "Ctrl + Alt + E")

        restored = Profile.from_dict(saved_data[0])
        reopened_dialog = ProfileEditorDialog(profile=restored)
        self.assertTrue(reopened_dialog.hotkey_enabled_check.isChecked())
        self.assertEqual(
            reopened_dialog.hotkey_sets[0]["keys"].get_hotkey_string(),
            "Ctrl + Alt + E",
        )
        self.assertEqual(
            reopened_dialog.hotkey_sets[1]["keys"].get_hotkey_string(),
            "Ctrl + Shift + F",
        )

    def test_hotkey_parser_accepts_editor_combination(self):
        modifiers, key_code = parse_hotkey_combination("Ctrl + Alt + E")

        self.assertEqual(modifiers, ModifierKeys.CTRL | ModifierKeys.ALT)
        self.assertEqual(key_code, ord("E"))

    def test_pywin32_none_return_registers_and_unregisters_hotkey(self):
        manager = HotkeyManager(include_default_hotkeys=False)
        definition = HotkeyDefinition(
            id="none-return",
            name="None return test",
            modifiers=ModifierKeys.CTRL | ModifierKeys.ALT,
            key_code=0x87,
            action=HotkeyAction.APPLY_PROFILE,
        )
        self.assertTrue(manager.add_hotkey(definition))

        with patch("core.hotkey_manager.RegisterHotKey", return_value=None):
            self.assertTrue(manager.register_hotkey(definition.id))
        self.assertEqual(manager.get_registered_hotkeys(), [definition.id])

        with patch("core.hotkey_manager.UnregisterHotKey", return_value=None):
            self.assertTrue(manager.unregister_hotkey(definition.id))
        self.assertEqual(manager.get_registered_hotkeys(), [])
        manager.shutdown()

    def test_native_filter_dispatches_registered_hotkey(self):
        manager = HotkeyManager(include_default_hotkeys=False)
        definition = HotkeyDefinition(
            id="native-filter",
            name="Native filter test",
            modifiers=ModifierKeys.CTRL | ModifierKeys.ALT,
            key_code=0x87,
            action=HotkeyAction.APPLY_PROFILE,
        )
        manager.hotkeys[definition.id] = definition
        manager.registered_hotkeys[73] = definition.id
        activated = []
        manager.hotkey_activated.connect(
            lambda hotkey_id, action: activated.append((hotkey_id, action))
        )

        message = wintypes.MSG()
        message.message = win32con.WM_HOTKEY
        message.wParam = 73
        handled, _result = manager.native_event_filter.nativeEventFilter(
            b"windows_generic_MSG",
            ctypes.addressof(message),
        )

        self.assertTrue(handled)
        self.assertEqual(
            activated,
            [(definition.id, HotkeyAction.APPLY_PROFILE.value)],
        )
        manager.registered_hotkeys.clear()
        manager.shutdown()

    def test_profile_hotkeys_are_registered_for_enabled_profiles(self):
        self.profile.hotkey_enabled = True
        self.profile.hotkey_sets = [
            {
                "enabled": True,
                "combination": "Ctrl + Alt + E",
                "action": "apply_profile",
            }
        ]
        hotkey_manager = FakeProfileHotkeyManager()
        window = type("Window", (), {})()
        window.profile_manager = FakeProfileManager([self.profile])
        window.profile_hotkey_manager = hotkey_manager

        result = WindowResizerMainWindow._sync_profile_hotkeys(window)

        self.assertTrue(hotkey_manager.cleared)
        self.assertEqual(len(hotkey_manager.registered), 1)
        self.assertEqual(result["failed"], [])
        definition = next(iter(hotkey_manager.hotkeys.values()))
        self.assertEqual(definition.modifiers, ModifierKeys.CTRL | ModifierKeys.ALT)
        self.assertEqual(definition.key_code, ord("E"))
        self.assertEqual(definition.action, HotkeyAction.APPLY_PROFILE)
        self.assertEqual(definition.parameters["profile_id"], self.profile.id)


if __name__ == "__main__":
    unittest.main()
