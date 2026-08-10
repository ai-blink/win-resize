"""Regression tests for the persisted application UI scale."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtCore import QPoint, QRect, QSize
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget

from gui.ui_scale_manager import (
    DEFAULT_UI_SCALE_PERCENT,
    UiScaleManager,
    UiScaleSettingsDialog,
    get_ui_scale_manager,
)


class MemorySettings:
    """Small QSettings substitute that keeps scale tests out of user settings."""

    def __init__(self, values=None):
        self.values = dict(values or {})
        self.sync_calls = 0

    def value(self, key, default=None, **_kwargs):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value

    def sync(self):
        self.sync_calls += 1


class UiScaleManagerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.original_font = self.app.font()

    def tearDown(self):
        self.app.setFont(self.original_font)

    def test_default_is_smaller_and_persisted_values_are_clamped(self):
        settings = MemorySettings()
        manager = UiScaleManager(settings)

        self.assertEqual(manager.scale_percent, DEFAULT_UI_SCALE_PERCENT)
        self.assertEqual(manager.set_scale(111), 110)
        self.assertEqual(settings.values["scale_percent"], 110)
        self.assertGreaterEqual(settings.sync_calls, 1)

        restored = UiScaleManager(settings)
        self.assertEqual(restored.scale_percent, 110)
        self.assertEqual(restored.set_scale(999), 125)

    def test_main_window_size_is_persisted_separately_from_scale(self):
        settings = MemorySettings()
        manager = UiScaleManager(settings)

        manager.save_main_window_size(QSize(1000, 700))
        manager.save_main_window_position(QPoint(250, 180))

        self.assertEqual(manager.load_main_window_size(), QSize(1000, 700))
        self.assertEqual(manager.load_main_window_position(), QPoint(250, 180))
        restored = UiScaleManager(settings)
        self.assertEqual(restored.load_main_window_size(), QSize(1000, 700))
        self.assertEqual(restored.load_main_window_position(), QPoint(250, 180))

    def test_registered_geometry_and_stylesheet_do_not_scale_cumulatively(self):
        manager = UiScaleManager(MemorySettings())
        manager.initialize_application()
        window = QWidget()
        window.setFixedSize(100, 50)
        window.setStyleSheet("QWidget { padding: 5px; font-size: 10pt; }")
        layout = QVBoxLayout(window)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        manager.register_window(window)
        self.assertEqual(window.minimumWidth(), 90)
        self.assertIn("padding: 4px", window.styleSheet())
        self.assertIn("font-size: 9pt", window.styleSheet())

        manager.set_scale(125, persist=False)
        self.assertEqual(window.minimumWidth(), 125)
        self.assertIn("padding: 6px", window.styleSheet())
        self.assertIn("font-size: 12.5pt", window.styleSheet())

        manager.set_scale(DEFAULT_UI_SCALE_PERCENT, persist=False)
        self.assertEqual(window.minimumWidth(), 90)
        self.assertIn("padding: 4px", window.styleSheet())
        self.assertIn("font-size: 9pt", window.styleSheet())

    def test_slider_applies_and_persists_each_selected_step(self):
        settings = MemorySettings()
        manager = UiScaleManager(settings)
        manager.initialize_application()
        dialog = UiScaleSettingsDialog(manager)

        dialog.scale_slider.setValue(115)

        self.assertEqual(manager.scale_percent, 115)
        self.assertEqual(settings.values["scale_percent"], 115)
        self.assertEqual(dialog.value_label.text(), "115%")

        dialog._reset_scale()
        self.assertEqual(manager.scale_percent, DEFAULT_UI_SCALE_PERCENT)
        self.assertEqual(dialog.scale_slider.value(), DEFAULT_UI_SCALE_PERCENT)
        dialog.close()


class MainWindowUiScaleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.manager = get_ui_scale_manager()
        self.original_scale = self.manager.scale_percent
        self.manager.set_scale(DEFAULT_UI_SCALE_PERCENT, persist=False)

        from gui.main_window import WindowResizerMainWindow

        self.window = WindowResizerMainWindow()

    def tearDown(self):
        self.window._quit_requested = True
        self.window.close()
        self.manager.set_scale(self.original_scale, persist=False)

    def test_main_profile_controls_follow_live_scale_changes(self):
        self.assertEqual(self.window.profile_button_bar.height(), 41)
        self.assertEqual(self.window.edit_profile_button.height(), 31)

        self.manager.set_scale(125, persist=False)

        self.assertEqual(self.window.profile_button_bar.height(), 58)
        self.assertEqual(self.window.edit_profile_button.height(), 42)
        self.assertEqual(self.window.window_list_widget.columnWidth(1), 100)

    def test_main_window_restores_and_saves_last_geometry(self):
        from gui import main_window as main_window_module

        settings = MemorySettings({
            "main_window_size": QSize(800, 600),
            "main_window_position": QPoint(500, 200),
        })
        manager = UiScaleManager(settings)
        with patch.object(main_window_module, "get_ui_scale_manager", return_value=manager):
            window = main_window_module.WindowResizerMainWindow()
            try:
                self.assertEqual(window.size(), QSize(800, 600))
                self.assertEqual(window.pos(), QPoint(0, 0))
                window.resize(800, 600)
                window.move(0, 0)
                window._save_main_window_geometry()
            finally:
                window._quit_requested = True
                window.close()

        self.assertEqual(manager.load_main_window_size(), QSize(800, 600))
        self.assertEqual(manager.load_main_window_position(), QPoint(0, 0))

    def test_main_window_position_is_clamped_to_its_available_screen(self):
        from gui.main_window import WindowResizerMainWindow

        available_geometry = QRect(-1280, 0, 1280, 720)
        self.assertEqual(
            WindowResizerMainWindow.clamp_main_window_position(
                QPoint(-600, 100), QSize(900, 700), available_geometry
            ),
            QPoint(-900, 20),
        )


if __name__ == "__main__":
    unittest.main()
