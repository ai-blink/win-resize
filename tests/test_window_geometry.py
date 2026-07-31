#!/usr/bin/env python3
"""Regression tests for DPI-safe main-window and position-preset geometry."""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication, QTableWidgetItem

from core.profile_manager import WindowConfiguration
from core.windows_api import WindowRect
from gui.main_window import ProfilePreviewOverlay, WindowInfo, WindowResizerMainWindow


class FakeScreen:
    def __init__(self, geometry, scale_factor):
        self._geometry = geometry
        self._scale_factor = scale_factor

    def geometry(self):
        return self._geometry

    def devicePixelRatio(self):
        return self._scale_factor


class WindowGeometryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        window = WindowResizerMainWindow()
        window.refresh_window_list = lambda: None
        return window

    def close_window(self, window):
        window._quit_requested = True
        window.close()

    def test_initial_constraints_fit_available_work_area(self):
        constraints = WindowResizerMainWindow.calculate_window_size_constraints(
            QRect(56, 0, 1864, 1080)
        )
        self.assertEqual(constraints, (900, 720, 1600, 1000, 1150, 800))

        small_screen_constraints = WindowResizerMainWindow.calculate_window_size_constraints(
            QRect(0, 0, 1366, 728)
        )
        self.assertEqual(small_screen_constraints, (900, 720, 1366, 728, 1150, 728))

    def test_profile_preview_converts_native_geometry_on_high_dpi_screen(self):
        config = WindowConfiguration(x=1200, y=100, width=800, height=600)
        geometry = ProfilePreviewOverlay.native_geometry_to_qt_geometry(
            config,
            [FakeScreen(QRect(0, 0, 1920, 1080), 2.0)],
        )

        self.assertEqual((geometry.x(), geometry.y()), (600, 50))
        self.assertEqual((geometry.width(), geometry.height()), (400, 300))

    def test_profile_preview_uses_native_monitor_origin_on_mixed_dpi_screens(self):
        config = WindowConfiguration(x=2600, y=100, width=800, height=600)
        geometry = ProfilePreviewOverlay.native_geometry_to_qt_geometry(
            config,
            [
                FakeScreen(QRect(0, 0, 1707, 960), 1.5),
                FakeScreen(QRect(1707, 0, 1920, 1080), 1.0),
            ],
            [
                QRect(0, 0, 2560, 1440),
                QRect(2560, 0, 1920, 1080),
            ],
        )

        self.assertEqual((geometry.x(), geometry.y()), (1747, 100))
        self.assertEqual((geometry.width(), geometry.height()), (800, 600))

    def test_position_preset_uses_native_work_area_and_preserves_offsets(self):
        x, y = WindowResizerMainWindow.calculate_position_in_work_area(
            "right", 800, 600, (-1920, 0, 0, 1040), margin=50
        )
        self.assertEqual((x, y), (-850, 220))

        x, y = WindowResizerMainWindow.calculate_position_in_work_area(
            "right", 800, 600, (0, 0, 3840, 2160), margin=50
        )
        self.assertEqual((x, y), (2990, 780))

    def test_apply_position_preset_uses_selected_window_work_area(self):
        window = self.make_window()
        try:
            window.window_list_widget.setRowCount(1)
            window.window_list_widget.setItem(0, 1, QTableWidgetItem("42"))
            window.window_list_widget.setCurrentCell(0, 1)
            window.width_spinbox.setValue(800)
            window.height_spinbox.setValue(600)
            window.get_work_area_for_window = lambda hwnd: (0, 0, 3840, 2160)
            applied = []
            window.apply_coordinates = lambda: applied.append(
                (window.x_spinbox.value(), window.y_spinbox.value())
            )

            window.apply_position_preset("right")

            self.assertEqual(applied, [(2990, 780)])
        finally:
            self.close_window(window)


if __name__ == "__main__":
    unittest.main()
