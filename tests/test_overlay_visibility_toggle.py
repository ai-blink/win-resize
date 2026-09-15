#!/usr/bin/env python3
"""Regression tests for hiding overlay buttons behind a small switch.

감추기는 버튼을 없애는 것이 아니라 보이기만 끄는 것이다. 다시 켜면 같은
자리에 그대로 돌아와야 하고, 스위치 자신은 절대 감춰지면 안 된다. 스위치가
감춰지면 되살릴 방법이 사라진다.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtCore import QEvent, QPoint, QSettings, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication

from core.profile_manager import OverlayStyle, ProfileManager, WindowConfiguration
from gui.main_window import WindowResizerMainWindow
from gui.overlay_toggle_button import OverlayToggleButton


class OverlayToggleButtonTests(unittest.TestCase):
    """스위치 위젯 자체의 동작."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _click(self, button):
        press = QMouseEvent(
            QEvent.MouseButtonPress, QPoint(5, 5),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
        )
        release = QMouseEvent(
            QEvent.MouseButtonRelease, QPoint(5, 5),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
        )
        button.mousePressEvent(press)
        button.mouseReleaseEvent(release)

    def test_click_toggles_and_reports(self):
        button = OverlayToggleButton()
        received = []
        button.toggled_hidden.connect(received.append)

        self._click(button)
        self.assertTrue(button.overlays_hidden)
        self.assertEqual(received, [True])

        self._click(button)
        self.assertFalse(button.overlays_hidden)
        self.assertEqual(received, [True, False])

        button.deleteLater()

    def test_drag_does_not_toggle(self):
        """옮기려고 끈 것을 누른 것으로 오해하면 안 된다."""
        button = OverlayToggleButton()
        received = []
        button.toggled_hidden.connect(received.append)

        press = QMouseEvent(
            QEvent.MouseButtonPress, QPoint(5, 5),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
        )
        button.mousePressEvent(press)
        button._dragged = True  # 드래그가 일어난 상태
        release = QMouseEvent(
            QEvent.MouseButtonRelease, QPoint(60, 60),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
        )
        button.mouseReleaseEvent(release)

        self.assertEqual(received, [])
        self.assertFalse(button.overlays_hidden)
        button.deleteLater()

    def test_never_accepts_focus(self):
        button = OverlayToggleButton()
        self.assertEqual(button.focusPolicy(), Qt.NoFocus)
        self.assertTrue(button.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        self.assertTrue(button.windowFlags() & Qt.WindowStaysOnTopHint)
        self.assertTrue(button.testAttribute(Qt.WA_ShowWithoutActivating))
        button.deleteLater()

    def test_set_state_does_not_emit(self):
        """상태를 맞추는 호출이 다시 시그널을 내면 무한 왕복이 된다."""
        button = OverlayToggleButton()
        received = []
        button.toggled_hidden.connect(received.append)

        button.set_overlays_hidden(True)

        self.assertTrue(button.overlays_hidden)
        self.assertEqual(received, [])
        button.deleteLater()


class OverlayHidingTests(unittest.TestCase):
    """메인 창이 감추기를 다루는 방식."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="overlay_hide_test_")
        self.window = WindowResizerMainWindow()
        self.app.processEvents()

        self.window.overlay_settings = QSettings(
            os.path.join(self.temp_dir, "overlay.ini"), QSettings.IniFormat
        )
        self.window.profile_manager = ProfileManager(
            storage_path=os.path.join(self.temp_dir, "profiles")
        )
        self.window.overlay_buttons = []
        self.window.overlays_hidden = False

        self.profile = self.window.profile_manager.create_profile(
            name="감추기 프로필",
            window_config=WindowConfiguration(x=10, y=20, width=800, height=600),
            window_info={"title": "A", "process_name": "a.exe"},
        )
        style = self.profile.effective_overlay_style()
        style.enabled = True
        self.profile.overlay_style = style

    def tearDown(self):
        self.window.hide_overlay_toggle_button()
        for button in list(self.window.overlay_buttons):
            button.hide()
            button.deleteLater()
        self.window.overlay_buttons = []
        self.window._quit_requested = True
        self.window.close()
        self.app.processEvents()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_hiding_keeps_buttons_and_positions(self):
        """감추기는 버튼을 없애지 않는다. 다시 켜면 같은 자리여야 한다."""
        button = self.window.show_overlay_button_for_profile(self.profile, QPoint(300, 400))
        self.assertIsNotNone(button)

        self.window.set_overlays_hidden(True)

        self.assertEqual(len(self.window.overlay_buttons), 1, "버튼이 사라지면 안 된다")
        self.assertFalse(button.isVisible())

        self.window.set_overlays_hidden(False)

        self.assertTrue(button.isVisible())
        self.assertEqual(button.pos(), QPoint(300, 400))

    def test_hidden_state_survives_new_buttons(self):
        """감춘 상태에서 새로 만든 버튼이 혼자 튀어나오면 안 된다."""
        self.window.set_overlays_hidden(True)

        button = self.window.show_overlay_button_for_profile(self.profile, QPoint(120, 130))

        self.assertIsNotNone(button)
        self.assertFalse(button.isVisible())
        # 감춰져 있어도 창 핸들은 있어야 추적 제외가 걸린다.
        self.assertTrue(button.native_hwnd)

    def test_toggle_switch_drives_hiding(self):
        self.window.show_overlay_button_for_profile(self.profile, QPoint(300, 400))
        switch = self.window.show_overlay_toggle_button(QPoint(50, 50))
        self.assertIsNotNone(switch)

        switch.toggled_hidden.emit(True)

        self.assertTrue(self.window.overlays_hidden)
        self.assertFalse(self.window.overlay_buttons[0].isVisible())

    def test_switch_itself_is_never_hidden(self):
        """스위치까지 감춰지면 되살릴 방법이 없다."""
        switch = self.window.show_overlay_toggle_button(QPoint(50, 50))

        self.window.set_overlays_hidden(True)

        self.assertTrue(switch.isVisible())
        self.assertTrue(switch.overlays_hidden, "스위치 표시가 상태를 따라야 한다")

    def test_removing_switch_restores_visibility(self):
        """감춘 채 스위치를 없애면 버튼을 되살릴 수단이 사라진다."""
        button = self.window.show_overlay_button_for_profile(self.profile, QPoint(300, 400))
        self.window.show_overlay_toggle_button(QPoint(50, 50))
        self.window.set_overlays_hidden(True)

        self.window.hide_overlay_toggle_button()

        self.assertIsNone(self.window.overlay_toggle_button)
        self.assertFalse(self.window.overlays_hidden)
        self.assertTrue(button.isVisible())

    def test_hidden_state_is_persisted(self):
        self.window.set_overlays_hidden(True)
        self.assertEqual(self.window.overlay_settings.value("hidden"), "true")

        self.window.set_overlays_hidden(False)
        self.assertEqual(self.window.overlay_settings.value("hidden"), "false")

    def test_switch_position_is_persisted(self):
        self.window.show_overlay_toggle_button(QPoint(210, 220))
        self.window._save_overlay_toggle_position()

        restored = self.window._load_overlay_toggle_position()

        self.assertEqual(restored, QPoint(210, 220))

    def test_lock_applies_to_switch(self):
        switch = self.window.show_overlay_toggle_button(QPoint(50, 50))
        self.window.set_overlay_locked(True)
        self.assertTrue(switch.locked)

        self.window.set_overlay_locked(False)
        self.assertFalse(switch.locked)


if __name__ == "__main__":
    unittest.main()
