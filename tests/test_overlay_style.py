#!/usr/bin/env python3
"""Regression tests for per-profile overlay button appearance.

생김새는 프로필에 저장되고, 편집기에서 왕복하며, 떠 있는 버튼에 바로 반영되어야
한다. 저장된 값이 깨져 있어도 버튼은 그려져야 한다.
"""

import os
import sys
import unittest
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QApplication

from core.profile_manager import (
    OverlayStyle, Profile, WindowConfiguration, OVERLAY_SHAPES
)
from gui.overlay_button import (
    OverlayButton, build_overlay_path, paint_overlay_face, resolve_overlay_colors
)


class StubTracker:
    def get_target_window_info(self):
        return None

    def exclude_hwnd(self, hwnd):
        pass

    def unexclude_hwnd(self, hwnd):
        pass


class StubProfileManager:
    def apply_profile(self, profile_id, window_info):
        return True


class OverlayStyleDataTests(unittest.TestCase):
    """저장 형식과 값 보정."""

    def test_defaults_are_usable(self):
        style = OverlayStyle()
        self.assertIn(style.shape, OVERLAY_SHAPES)
        self.assertTrue(QColor(style.background_color).isValid())
        self.assertTrue(QColor(style.text_color).isValid())
        self.assertTrue(QColor(style.border_color).isValid())

    def test_unknown_shape_falls_back_to_pill(self):
        self.assertEqual(OverlayStyle(shape="삼각형").shape, "pill")

    def test_out_of_range_values_are_clamped(self):
        style = OverlayStyle(width=9999, height=1, border_width=99.0)
        self.assertLessEqual(style.width, 600)
        self.assertGreaterEqual(style.height, 28)
        self.assertLessEqual(style.border_width, 8.0)

    def test_from_dict_ignores_unknown_keys(self):
        style = OverlayStyle.from_dict({"shape": "circle", "잡음": 1, "label": "테스트"})
        self.assertEqual(style.shape, "circle")
        self.assertEqual(style.label, "테스트")

    def test_label_falls_back_to_profile_name(self):
        self.assertEqual(OverlayStyle(label="").resolved_label("블렌더"), "블렌더")
        self.assertEqual(OverlayStyle(label="  ").resolved_label("블렌더"), "블렌더")
        self.assertEqual(OverlayStyle(label="B").resolved_label("블렌더"), "B")

    def test_profile_round_trip_preserves_style(self):
        profile = Profile(
            name="스타일 프로필",
            window_config=WindowConfiguration(x=0, y=0, width=800, height=600),
            overlay_style=OverlayStyle(
                shape="circle", label="블", background_color="#aa3344",
                width=90, height=90, border_width=3.0
            ),
        )

        restored = Profile.from_dict(profile.to_dict())

        self.assertIsInstance(restored.overlay_style, OverlayStyle)
        self.assertEqual(restored.overlay_style.shape, "circle")
        self.assertEqual(restored.overlay_style.label, "블")
        self.assertEqual(restored.overlay_style.background_color, "#aa3344")
        self.assertEqual(restored.overlay_style.width, 90)

    def test_profile_without_style_gets_default(self):
        """생김새가 없던 옛 프로필도 그대로 열려야 한다."""
        profile = Profile(
            name="옛 프로필",
            window_config=WindowConfiguration(x=0, y=0, width=800, height=600),
        )
        data = profile.to_dict()
        data.pop('overlay_style', None)

        restored = Profile.from_dict(data)

        self.assertIsNone(restored.overlay_style)
        self.assertIsInstance(restored.effective_overlay_style(), OverlayStyle)


class OverlayPaintingTests(unittest.TestCase):
    """그리기 계층이 깨진 값에도 견디는지."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_every_shape_produces_a_path(self):
        rect = QRectF(0, 0, 150, 46)
        for shape in OVERLAY_SHAPES:
            path = build_overlay_path(rect, shape)
            self.assertFalse(path.isEmpty(), "{0} 모양이 빈 경로를 만들었다".format(shape))

    def test_invalid_colors_do_not_break_rendering(self):
        style = OverlayStyle(
            background_color="이건 색이 아니다",
            text_color="",
            border_color="#ZZZZZZ",
        )
        background, border, text = resolve_overlay_colors(style, 'idle')
        self.assertTrue(background.isValid())
        self.assertTrue(border.isValid())
        self.assertTrue(text.isValid())

    def test_feedback_state_overrides_profile_colors(self):
        """성공과 실패는 프로필 색에 묻히면 안 된다."""
        style = OverlayStyle(background_color="#aa3344")
        success, _, _ = resolve_overlay_colors(style, 'success')
        failure, _, _ = resolve_overlay_colors(style, 'failure')
        self.assertGreater(success.green(), success.red())
        self.assertGreater(failure.red(), failure.green())

    def test_paint_overlay_face_draws_without_error(self):
        image = QImage(200, 80, QImage.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        try:
            path = paint_overlay_face(
                painter, QRectF(5, 5, 190, 70), OverlayStyle(), "테스트", 'idle'
            )
        finally:
            painter.end()
        self.assertFalse(path.isEmpty())


class OverlayButtonStyleTests(unittest.TestCase):
    """버튼이 프로필 생김새를 실제로 반영하는지."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_button(self, style=None):
        return OverlayButton(
            "profile-1", "블렌더", StubProfileManager(), StubTracker(), style=style
        )

    def test_button_uses_style_size(self):
        button = self._make_button(OverlayStyle(width=220, height=64))
        self.assertEqual(button.width(), 220)
        self.assertEqual(button.height(), 64)
        button.deleteLater()

    def test_button_uses_label_when_set(self):
        button = self._make_button(OverlayStyle(label="블"))
        self.assertEqual(button.display_label(), "블")
        button.deleteLater()

    def test_button_falls_back_to_profile_name(self):
        button = self._make_button(OverlayStyle(label=""))
        self.assertEqual(button.display_label(), "블렌더")
        button.deleteLater()

    def test_set_style_updates_size_and_label(self):
        button = self._make_button(OverlayStyle())
        button.set_style(OverlayStyle(width=300, height=70, label="새 라벨"))

        self.assertEqual(button.width(), 300)
        self.assertEqual(button.height(), 70)
        self.assertEqual(button.display_label(), "새 라벨")
        button.deleteLater()

    def test_button_without_style_uses_defaults(self):
        button = self._make_button(None)
        self.assertIsInstance(button.style_settings, OverlayStyle)
        button.deleteLater()


class OverlayActivationTests(unittest.TestCase):
    """프로필별 발동 방식이 전역 설정을 이기는지."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _button(self, style, global_mode="click", global_dwell=800):
        from gui.overlay_button import OverlayButton
        return OverlayButton(
            "profile-1", "블렌더", StubProfileManager(), StubTracker(),
            mode=global_mode, dwell_ms=global_dwell, style=style
        )

    def test_global_activation_follows_global_mode(self):
        button = self._button(OverlayStyle(activation="global"), global_mode="dwell")
        self.assertEqual(button.mode, "dwell")
        button.deleteLater()

    def test_profile_activation_overrides_global(self):
        button = self._button(OverlayStyle(activation="click"), global_mode="dwell")
        self.assertEqual(button.mode, "click")

        other = self._button(OverlayStyle(activation="dwell"), global_mode="click")
        self.assertEqual(other.mode, "dwell")

        button.deleteLater()
        other.deleteLater()

    def test_zero_dwell_means_use_global(self):
        button = self._button(OverlayStyle(dwell_ms=0), global_dwell=1200)
        self.assertEqual(button.dwell_ms, 1200)
        button.deleteLater()

    def test_profile_dwell_overrides_global(self):
        button = self._button(OverlayStyle(dwell_ms=2000), global_dwell=800)
        self.assertEqual(button.dwell_ms, 2000)
        button.deleteLater()

    def test_global_change_does_not_override_profile_choice(self):
        button = self._button(OverlayStyle(activation="click"), global_mode="click")
        button.set_interaction_mode("dwell")
        self.assertEqual(button.mode, "click", "프로필이 정한 방식이 유지되어야 한다")
        button.deleteLater()

    def test_unknown_activation_falls_back_to_global(self):
        self.assertEqual(OverlayStyle(activation="눈짓").activation, "global")

    def test_dwell_ms_is_clamped_when_set(self):
        self.assertEqual(OverlayStyle(dwell_ms=50).dwell_ms, 200)
        self.assertEqual(OverlayStyle(dwell_ms=99999).dwell_ms, 5000)
        self.assertEqual(OverlayStyle(dwell_ms=0).dwell_ms, 0)


class OverlayGaugeTests(unittest.TestCase):
    """드웰 게이지 시각화."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _render(self, style, progress):
        from gui.overlay_button import paint_overlay_face
        image = QImage(160, 60, QImage.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        try:
            paint_overlay_face(
                painter, QRectF(4, 4, 152, 52), style, "테스트", 'idle', progress
            )
        finally:
            painter.end()
        return image

    def test_every_gauge_renders(self):
        from core.profile_manager import OVERLAY_GAUGES
        for gauge in OVERLAY_GAUGES:
            image = self._render(OverlayStyle(gauge=gauge), 0.6)
            self.assertFalse(image.isNull(), "{0} 게이지 렌더 실패".format(gauge))

    def test_unknown_gauge_falls_back_to_outline(self):
        self.assertEqual(OverlayStyle(gauge="반짝임").gauge, "outline")

    def test_gauge_changes_pixels_when_progressing(self):
        """게이지가 실제로 그려지는지 픽셀로 확인한다."""
        style = OverlayStyle(gauge="fill", gauge_color="#ff0000")
        empty = self._render(style, 0.0)
        filled = self._render(style, 1.0)
        self.assertNotEqual(empty.constBits().asstring(empty.byteCount()),
                            filled.constBits().asstring(filled.byteCount()))

    def test_none_gauge_draws_nothing(self):
        style = OverlayStyle(gauge="none")
        empty = self._render(style, 0.0)
        progressed = self._render(style, 1.0)
        self.assertEqual(empty.constBits().asstring(empty.byteCount()),
                         progressed.constBits().asstring(progressed.byteCount()))


class OverlayStyleEditorTests(unittest.TestCase):
    """편집기 탭이 값을 온전히 왕복하는지."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_editor_round_trips_style(self):
        from gui.profile_editor import ProfileEditorDialog

        dialog = ProfileEditorDialog()
        original = OverlayStyle(
            shape="rounded", label="스팀", background_color="#123456",
            text_color="#fedcba", border_color="#00ff00",
            border_width=2.5, width=180, height=52,
        )

        dialog._apply_overlay_style_to_widgets(original)
        collected = dialog._collect_overlay_style()

        self.assertEqual(asdict(collected), asdict(original))
        dialog.deleteLater()

    def test_appearance_is_locked_until_the_button_is_enabled(self):
        """켜지 않은 채 생김새만 만지면 다 해놓고도 버튼이 없다고 느낀다."""
        from gui.profile_editor import ProfileEditorDialog

        dialog = ProfileEditorDialog()

        dialog.overlay_enabled_check.setChecked(False)
        self.assertFalse(dialog.overlay_shape_group.isEnabled())
        self.assertFalse(dialog.overlay_color_group.isEnabled())
        self.assertFalse(dialog.overlay_preview_group.isEnabled())
        self.assertFalse(dialog.overlay_activation_group.isEnabled())

        dialog.overlay_enabled_check.setChecked(True)
        self.assertTrue(dialog.overlay_shape_group.isEnabled())
        self.assertTrue(dialog.overlay_color_group.isEnabled())
        self.assertTrue(dialog.overlay_activation_group.isEnabled())

        dialog.deleteLater()

    def test_reset_keeps_the_enabled_state(self):
        """되돌리기가 사용 여부까지 꺼서 버튼이 사라지면 안 된다."""
        from gui.profile_editor import ProfileEditorDialog

        dialog = ProfileEditorDialog()
        dialog.overlay_enabled_check.setChecked(True)
        dialog.overlay_label_edit.setText("바뀐 라벨")

        dialog._reset_overlay_style()

        self.assertTrue(dialog.overlay_enabled_check.isChecked())
        self.assertEqual(dialog._collect_overlay_style().label, "")
        dialog.deleteLater()

    def test_editor_tab_exists(self):
        from gui.profile_editor import ProfileEditorDialog

        dialog = ProfileEditorDialog()
        titles = [dialog.tab_widget.tabText(i) for i in range(dialog.tab_widget.count())]

        self.assertIn("오버레이 버튼", titles)
        dialog.deleteLater()

    def test_saved_payload_carries_style(self):
        from gui.profile_editor import ProfileEditorDialog

        dialog = ProfileEditorDialog()
        dialog._apply_overlay_style_to_widgets(OverlayStyle(shape="circle", label="원"))
        payload = asdict(dialog._collect_overlay_style())

        self.assertEqual(payload["shape"], "circle")
        self.assertEqual(payload["label"], "원")
        # 저장 형식은 순수 dict여야 한다. 그대로 json에 들어간다.
        self.assertTrue(all(isinstance(key, str) for key in payload))
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
