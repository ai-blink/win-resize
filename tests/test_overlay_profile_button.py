#!/usr/bin/env python3
"""Regression tests for the overlay profile button and foreground tracking.

이 기능의 핵심 계약은 하나다. 오버레이 버튼은 "사용자가 직전에 조작하던 창"에
프로필을 적용해야 하며, 오버레이 자신이나 본창이 대상이 되어서는 안 된다.
아래 테스트는 그 계약이 깨지는 경우를 잡는다.
"""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtWidgets import QApplication

import core.foreground_tracker as foreground_tracker
from core.foreground_tracker import ForegroundTracker
from gui.overlay_button import OverlayButton, MODE_CLICK, MODE_DWELL


class FakeWin32Gui:
    """foreground_tracker가 쓰는 win32gui 호출만 흉내 낸다."""

    def __init__(self):
        self.foreground = 0
        self.valid_windows = set()
        self.visible_windows = set()
        self.titles = {}
        self.classes = {}

    def GetForegroundWindow(self):
        return self.foreground

    def IsWindow(self, hwnd):
        return hwnd in self.valid_windows

    def IsWindowVisible(self, hwnd):
        return hwnd in self.visible_windows

    def GetWindowText(self, hwnd):
        return self.titles.get(hwnd, "")

    def GetClassName(self, hwnd):
        return self.classes.get(hwnd, "AppWindow")


class RecordingProfileManager:
    """apply_profile 호출을 기록한다."""

    def __init__(self, result=True):
        self.result = result
        self.calls = []

    def apply_profile(self, profile_id, window_info):
        self.calls.append((profile_id, window_info))
        return self.result


class StubTracker:
    def __init__(self, window_info=None):
        self.window_info = window_info
        self.excluded = set()

    def get_target_window_info(self):
        return self.window_info

    def exclude_hwnd(self, hwnd):
        self.excluded.add(int(hwnd))

    def unexclude_hwnd(self, hwnd):
        self.excluded.discard(int(hwnd))


class ForegroundTrackerTests(unittest.TestCase):
    """대상 창 선택 규칙."""

    def setUp(self):
        self.fake = FakeWin32Gui()
        self._original_win32gui = foreground_tracker.win32gui
        foreground_tracker.win32gui = self.fake

        # 일반 앱 창 하나와 오버레이 창 하나를 등록한다.
        for hwnd in (100, 200):
            self.fake.valid_windows.add(hwnd)
            self.fake.visible_windows.add(hwnd)
        self.fake.titles[100] = "대상 앱"
        self.fake.titles[200] = "오버레이"

        self.tracker = ForegroundTracker()

    def tearDown(self):
        foreground_tracker.win32gui = self._original_win32gui

    def test_tracks_current_foreground_window(self):
        self.fake.foreground = 100
        self.assertEqual(self.tracker.get_target_hwnd(), 100)

    def test_excluded_window_does_not_become_target(self):
        """오버레이나 본창이 앞에 와도 직전 대상이 유지되어야 한다."""
        self.fake.foreground = 100
        self.assertEqual(self.tracker.get_target_hwnd(), 100)

        self.tracker.exclude_hwnd(200)
        self.fake.foreground = 200

        self.assertEqual(
            self.tracker.get_target_hwnd(), 100,
            "제외된 창이 앞에 오면 직전 대상을 유지해야 한다",
        )

    def test_shell_window_does_not_become_target(self):
        self.fake.foreground = 100
        self.assertEqual(self.tracker.get_target_hwnd(), 100)

        self.fake.valid_windows.add(300)
        self.fake.visible_windows.add(300)
        self.fake.classes[300] = "Shell_TrayWnd"
        self.fake.foreground = 300

        self.assertEqual(self.tracker.get_target_hwnd(), 100)

    def test_closed_target_returns_none(self):
        self.fake.foreground = 100
        self.assertEqual(self.tracker.get_target_hwnd(), 100)

        self.fake.foreground = 0
        self.fake.valid_windows.discard(100)

        self.assertIsNone(self.tracker.get_target_hwnd())

    def test_unexclude_restores_eligibility(self):
        self.tracker.exclude_hwnd(200)
        self.assertTrue(self.tracker.is_excluded(200))

        self.tracker.unexclude_hwnd(200)
        self.fake.foreground = 200

        self.assertEqual(self.tracker.get_target_hwnd(), 200)


class OverlayButtonTests(unittest.TestCase):
    """버튼 발동이 대상 창과 프로필을 올바르게 연결하는지."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_trigger_applies_profile_to_tracked_window(self):
        window_info = {"hwnd": 4242, "title": "대상 앱"}
        manager = RecordingProfileManager(result=True)
        tracker = StubTracker(window_info)

        button = OverlayButton("profile-1", "게임 배치", manager, tracker)
        received = []
        button.profile_applied.connect(lambda ok, msg: received.append((ok, msg)))

        button.trigger()

        self.assertEqual(len(manager.calls), 1)
        profile_id, passed_info = manager.calls[0]
        self.assertEqual(profile_id, "profile-1")
        self.assertEqual(passed_info["hwnd"], 4242)
        self.assertTrue(received[0][0])

        button.deleteLater()

    def test_trigger_without_target_does_not_apply(self):
        manager = RecordingProfileManager(result=True)
        tracker = StubTracker(None)

        button = OverlayButton("profile-1", "게임 배치", manager, tracker)
        received = []
        button.profile_applied.connect(lambda ok, msg: received.append((ok, msg)))

        button.trigger()

        self.assertEqual(manager.calls, [], "대상 창이 없으면 적용을 시도하지 않는다")
        self.assertFalse(received[0][0])

        button.deleteLater()

    def test_failed_application_reports_failure(self):
        manager = RecordingProfileManager(result=False)
        tracker = StubTracker({"hwnd": 4242, "title": "대상 앱"})

        button = OverlayButton("profile-1", "게임 배치", manager, tracker)
        received = []
        button.profile_applied.connect(lambda ok, msg: received.append((ok, msg)))

        button.trigger()

        self.assertEqual(len(manager.calls), 1)
        self.assertFalse(received[0][0])

        button.deleteLater()

    def test_apply_error_is_contained(self):
        """적용 중 예외가 나도 버튼이 죽지 않고 실패로 보고한다."""

        class ExplodingManager:
            def apply_profile(self, profile_id, window_info):
                raise RuntimeError("창 조작 실패")

        tracker = StubTracker({"hwnd": 4242, "title": "대상 앱"})
        button = OverlayButton("profile-1", "게임 배치", ExplodingManager(), tracker)
        received = []
        button.profile_applied.connect(lambda ok, msg: received.append((ok, msg)))

        button.trigger()

        self.assertFalse(received[0][0])
        self.assertIn("창 조작 실패", received[0][1])

        button.deleteLater()

    def test_dwell_mode_fires_without_click(self):
        """드웰 모드에서는 머무르는 것만으로 발동해야 한다."""
        manager = RecordingProfileManager()
        button = self._make_dwell_button(manager, dwell_ms=200)

        button.enterEvent(QEvent(QEvent.Enter))
        self.assertGreater(button.dwell_progress(), -1.0)

        self._run_dwell_ticks(button, 12)

        self.assertEqual(len(manager.calls), 1, "드웰이 끝나면 한 번 발동해야 한다")
        button.deleteLater()

    def test_dwell_does_not_repeat_until_pointer_leaves(self):
        """머무르는 동안 반복 발동하면 창이 계속 튄다."""
        manager = RecordingProfileManager()
        button = self._make_dwell_button(manager, dwell_ms=200)

        button.enterEvent(QEvent(QEvent.Enter))
        self._run_dwell_ticks(button, 12)
        self.assertEqual(len(manager.calls), 1)

        # 마우스가 그대로 있는 상태에서 시간이 더 흘러도 다시 발동하지 않는다.
        self._run_dwell_ticks(button, 12)
        self.assertEqual(len(manager.calls), 1)

        # 나갔다 들어오면 다시 발동할 수 있다.
        button.leaveEvent(QEvent(QEvent.Leave))
        button.enterEvent(QEvent(QEvent.Enter))
        self._run_dwell_ticks(button, 12)
        self.assertEqual(len(manager.calls), 2)

        button.deleteLater()

    def test_click_mode_does_not_dwell(self):
        """클릭 모드에서 마우스를 올려두기만 하면 발동하면 안 된다."""
        manager = RecordingProfileManager()
        button = OverlayButton(
            "profile-1", "게임 배치", manager,
            StubTracker({"hwnd": 4242, "title": "대상 앱"}),
            mode=MODE_CLICK,
        )

        button.enterEvent(QEvent(QEvent.Enter))
        self._run_dwell_ticks(button, 10)

        self.assertEqual(manager.calls, [])
        button.deleteLater()

    def test_switching_mode_cancels_pending_dwell(self):
        manager = RecordingProfileManager()
        button = self._make_dwell_button(manager, dwell_ms=1000)

        button.enterEvent(QEvent(QEvent.Enter))
        button._on_dwell_tick()
        self.assertGreater(button.dwell_progress(), 0.0)

        button.set_interaction_mode(MODE_CLICK)

        self.assertEqual(button.dwell_progress(), 0.0)
        self.assertEqual(manager.calls, [])
        button.deleteLater()

    def test_drag_cancels_dwell(self):
        """배치하려고 누른 것을 발동으로 오해하면 안 된다."""
        from PyQt5.QtCore import QPoint
        from PyQt5.QtGui import QMouseEvent

        manager = RecordingProfileManager()
        button = self._make_dwell_button(manager, dwell_ms=1000)

        button.enterEvent(QEvent(QEvent.Enter))
        button._on_dwell_tick()
        self.assertGreater(button.dwell_progress(), 0.0)

        press = QMouseEvent(
            QEvent.MouseButtonPress, QPoint(5, 5),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
        )
        button.mousePressEvent(press)

        self.assertEqual(button.dwell_progress(), 0.0)
        self.assertEqual(manager.calls, [])
        button.deleteLater()

    def _make_dwell_button(self, manager, dwell_ms):
        return OverlayButton(
            "profile-1", "게임 배치", manager,
            StubTracker({"hwnd": 4242, "title": "대상 앱"}),
            mode=MODE_DWELL, dwell_ms=dwell_ms,
        )

    def _run_dwell_ticks(self, button, count):
        """타이머를 실제로 기다리지 않고 틱만 진행시킨다."""
        for _ in range(count):
            if not button._dwell_timer.isActive():
                break
            button._on_dwell_tick()

    def test_button_never_accepts_focus(self):
        """활성화되면 대상 창을 잃는다. 포커스 정책은 회귀하면 안 된다."""
        from PyQt5.QtCore import Qt

        button = OverlayButton("profile-1", "게임 배치", RecordingProfileManager(), StubTracker())

        self.assertEqual(button.focusPolicy(), Qt.NoFocus)
        self.assertTrue(button.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        self.assertTrue(button.windowFlags() & Qt.WindowStaysOnTopHint)
        self.assertTrue(button.testAttribute(Qt.WA_ShowWithoutActivating))

        button.deleteLater()


if __name__ == "__main__":
    unittest.main()
