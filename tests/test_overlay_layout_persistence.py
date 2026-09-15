#!/usr/bin/env python3
"""Regression tests for overlay button layout persistence.

오버레이 배치는 앱을 다시 켜도 그대로 남아야 한다. 동시에 복원이 두 번
불려도 같은 버튼이 겹쳐 쌓이면 안 된다. 실제로 중복이 발생한 적이 있어
그 두 가지를 여기서 고정한다.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtCore import QPoint, QSettings
from PyQt5.QtWidgets import QApplication

from core.profile_manager import ProfileManager, WindowConfiguration
from gui.main_window import WindowResizerMainWindow
from gui.overlay_button import MODE_CLICK, MODE_DWELL


class OverlayLayoutPersistenceTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="overlay_layout_test_")
        self.window = WindowResizerMainWindow()

        # 초기화가 예약한 복원을 먼저 소화시킨 뒤 사용자 설정에서 분리한다.
        self.app.processEvents()
        self.window.overlay_settings = QSettings(
            os.path.join(self.temp_dir, "overlay.ini"), QSettings.IniFormat
        )
        self.window.profile_manager = ProfileManager(
            storage_path=os.path.join(self.temp_dir, "profiles")
        )
        self.window.overlay_buttons = []

        self.first = self.window.profile_manager.create_profile(
            name="첫 배치",
            window_config=WindowConfiguration(x=10, y=20, width=800, height=600),
            window_info={"title": "A", "process_name": "a.exe"},
        )
        self.second = self.window.profile_manager.create_profile(
            name="둘째 배치",
            window_config=WindowConfiguration(x=30, y=40, width=900, height=700),
            window_info={"title": "B", "process_name": "b.exe"},
        )

    def tearDown(self):
        for button in list(self.window.overlay_buttons):
            button.hide()
            button.deleteLater()
        self.window.overlay_buttons = []
        self.window._quit_requested = True
        self.window.close()
        self.app.processEvents()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -- 도우미 -------------------------------------------------------

    def _add_button(self, profile, position):
        # 무엇을 띄울지는 프로필의 사용 여부가 정한다. 복원도 그것을 본다.
        style = profile.effective_overlay_style()
        style.enabled = True
        profile.overlay_style = style

        button = self.window._create_overlay_button(profile)
        button.move(position)
        button.show()
        self.window.overlay_buttons.append(button)
        return button

    def _stored_layout(self):
        return json.loads(self.window.overlay_settings.value("layout", "[]"))

    def _clear_buttons(self):
        for button in list(self.window.overlay_buttons):
            button.hide()
            button.deleteLater()
        self.window.overlay_buttons = []
        self.app.processEvents()

    # -- 테스트 -------------------------------------------------------

    def test_layout_round_trip(self):
        self._add_button(self.first, QPoint(150, 250))
        self._add_button(self.second, QPoint(400, 600))
        self.window.save_overlay_layout()

        self._clear_buttons()
        self.window.restore_overlay_buttons()

        self.assertEqual(len(self.window.overlay_buttons), 2)
        self.assertEqual(
            {b.profile_id for b in self.window.overlay_buttons},
            {self.first.id, self.second.id},
        )

        # 복원 순서는 계약이 아니다. 프로필별 좌표가 맞는지로 판정한다.
        by_profile = {b.profile_id: b.pos() for b in self.window.overlay_buttons}
        self.assertEqual(by_profile[self.first.id], QPoint(150, 250))
        self.assertEqual(by_profile[self.second.id], QPoint(400, 600))

    def test_restore_twice_does_not_duplicate(self):
        """복원이 두 번 불려도 같은 버튼이 겹쳐 쌓이면 안 된다."""
        self._add_button(self.first, QPoint(150, 250))
        self.window.save_overlay_layout()
        self._clear_buttons()

        self.window.restore_overlay_buttons()
        self.window.restore_overlay_buttons()

        self.assertEqual(len(self.window.overlay_buttons), 1)
        self.assertEqual(len(self._stored_layout()), 1)

    def test_deleted_profile_is_dropped_from_layout(self):
        self._add_button(self.first, QPoint(150, 250))
        self._add_button(self.second, QPoint(400, 600))
        self.window.save_overlay_layout()
        self._clear_buttons()

        self.window.profile_manager.delete_profile(self.second.id)
        self.window.restore_overlay_buttons()

        self.assertEqual(len(self.window.overlay_buttons), 1)
        self.assertEqual(len(self._stored_layout()), 1)

    def test_mode_change_propagates_to_all_buttons(self):
        self._add_button(self.first, QPoint(150, 250))
        self._add_button(self.second, QPoint(400, 600))

        self.window.set_overlay_mode(MODE_DWELL)
        self.assertTrue(all(b.mode == MODE_DWELL for b in self.window.overlay_buttons))

        self.window.set_overlay_mode(MODE_CLICK)
        self.assertTrue(all(b.mode == MODE_CLICK for b in self.window.overlay_buttons))

    def test_lock_propagates_to_all_buttons(self):
        self._add_button(self.first, QPoint(150, 250))
        self._add_button(self.second, QPoint(400, 600))

        self.window.set_overlay_locked(True)
        self.assertTrue(all(b.locked for b in self.window.overlay_buttons))

        self.window.set_overlay_locked(False)
        self.assertFalse(any(b.locked for b in self.window.overlay_buttons))

    def test_unknown_stored_mode_falls_back_to_click(self):
        self.window.overlay_settings.setValue("interaction_mode", "손짓")
        self.assertEqual(self.window._load_overlay_mode(), MODE_CLICK)

    def test_enabling_in_editor_creates_the_button(self):
        """편집 창에서 켜고 저장하면 화면에 버튼이 나타나야 한다."""
        from dataclasses import asdict
        from core.profile_manager import OverlayStyle

        self.window._assign_overlay_style(
            self.first, {'overlay_style': asdict(OverlayStyle(enabled=True))}
        )
        self.window.refresh_overlay_buttons_for_profile(self.first)

        self.assertEqual(len(self.window.overlay_buttons), 1)
        self.assertEqual(self.window.overlay_buttons[0].profile_id, self.first.id)

    def test_disabling_in_editor_removes_the_button(self):
        from dataclasses import asdict
        from core.profile_manager import OverlayStyle

        self._add_button(self.first, QPoint(150, 250))
        self.assertEqual(len(self.window.overlay_buttons), 1)

        self.window._assign_overlay_style(
            self.first, {'overlay_style': asdict(OverlayStyle(enabled=False))}
        )
        self.window.refresh_overlay_buttons_for_profile(self.first)

        self.assertEqual(self.window.overlay_buttons, [])

    def test_disabled_profile_is_not_restored(self):
        self._add_button(self.first, QPoint(150, 250))
        self.window.save_overlay_layout()
        self._clear_buttons()

        style = self.first.effective_overlay_style()
        style.enabled = False
        self.first.overlay_style = style

        self.window.restore_overlay_buttons()

        self.assertEqual(self.window.overlay_buttons, [])

    def test_closing_a_button_turns_the_profile_off(self):
        """닫은 버튼이 다음 실행에 되살아나면 사용자는 껐다고 생각하지 않는다."""
        button = self._add_button(self.first, QPoint(150, 250))

        button.close()
        self.window._on_overlay_button_closed(button)

        self.assertFalse(self.first.effective_overlay_style().enabled)

    def test_corrupt_layout_does_not_raise(self):
        self.window.overlay_settings.setValue("layout", "{이건 json이 아니다")

        self.window.restore_overlay_buttons()

        self.assertEqual(self.window.overlay_buttons, [])


if __name__ == "__main__":
    unittest.main()
