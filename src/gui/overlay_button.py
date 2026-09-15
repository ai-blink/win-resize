"""
Overlay Profile Button
======================

화면 어디에나 배치할 수 있는 떠 있는 버튼이다. 누르면 사용자가 직전에
조작하던 창에 지정된 프로필을 적용한다.

설계 핵심:
이 창은 절대 활성화되지 않아야 한다. 활성화되는 순간 "현재 활성 창"이
오버레이 자신으로 바뀌어 엉뚱한 창에 프로필을 적용하게 된다. 그래서
Qt 플래그(WindowDoesNotAcceptFocus, WA_ShowWithoutActivating)와 네이티브
확장 스타일(WS_EX_NOACTIVATE)을 함께 건다. Qt 플래그만으로는 환경에 따라
활성화가 새어 나가기 때문에 두 겹으로 막는다.

WS_EX_TOOLWINDOW는 작업표시줄과 Alt+Tab 목록에서 이 버튼을 감춘다.
"""

import ctypes
import logging
from typing import Optional

from PyQt5.QtCore import QPoint, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QAction, QMenu, QWidget

logger = logging.getLogger(__name__)

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080

# 이 거리보다 적게 움직였으면 배치가 아니라 클릭으로 본다.
DRAG_THRESHOLD_PX = 5

# 적용 결과 색을 보여주는 시간.
FEEDBACK_DURATION_MS = 900

DEFAULT_WIDTH = 150
DEFAULT_HEIGHT = 46

# 프로필이 잘못된 색 문자열을 들고 있어도 버튼은 보여야 한다.
OVERLAY_FALLBACK_BACKGROUND = "#262A34"
OVERLAY_FALLBACK_TEXT = "#E8ECF4"
OVERLAY_FALLBACK_BORDER = "#6E7687"
OVERLAY_FALLBACK_GAUGE = "#78C8FF"

# 발동 방식. 전역 토글로 모든 버튼에 같은 값이 적용된다.
MODE_CLICK = 'click'
MODE_DWELL = 'dwell'

# 머무른 채 이 시간이 지나면 발동한다.
DEFAULT_DWELL_MS = 800

# 진행 링 갱신 주기. 30fps면 눈에 매끄럽고 CPU 부담이 적다.
DWELL_TICK_MS = 33

# 진행 링 두께.
DWELL_RING_WIDTH = 3.0


def apply_no_activate_style(widget) -> int:
    """떠 있는 위젯이 절대 활성화되지 않도록 네이티브 확장 스타일을 건다.

    활성화되는 순간 "직전에 쓰던 창"이 이 위젯으로 바뀐다. 오버레이 계열
    위젯은 전부 이 처리를 거쳐야 한다. 실패해도 Qt 플래그가 남아 있으므로
    호출한 쪽을 멈추지는 않는다. 돌려주는 값은 이 위젯의 창 핸들이다.
    """
    try:
        hwnd = int(widget.winId())
        user32 = ctypes.windll.user32
        current = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, current | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        )
        return hwnd
    except Exception as exc:
        logger.warning("오버레이 확장 스타일 적용 실패: %s", exc)
        try:
            return int(widget.winId())
        except Exception:
            return 0


def _default_overlay_style():
    """프로필이 생김새를 갖고 있지 않을 때 쓸 기본값."""
    from core.profile_manager import OverlayStyle
    return OverlayStyle()


def build_overlay_path(rect: QRectF, shape: str) -> QPainterPath:
    """모양 이름에 맞는 외곽선 경로를 만든다."""
    path = QPainterPath()

    if shape == 'circle':
        side = min(rect.width(), rect.height())
        center = rect.center()
        square = QRectF(
            center.x() - side / 2.0, center.y() - side / 2.0, side, side
        )
        path.addEllipse(square)
    elif shape == 'rectangle':
        path.addRect(rect)
    elif shape == 'rounded':
        path.addRoundedRect(rect, 10.0, 10.0)
    else:  # pill
        radius = rect.height() / 2.0
        path.addRoundedRect(rect, radius, radius)

    return path


def resolve_overlay_colors(style, state: str):
    """상태에 맞는 배경, 테두리, 글자 색을 정한다.

    적용 결과(success, failure)는 프로필 색을 무시하고 고정 색을 쓴다.
    결과 피드백이 프로필 색에 묻히면 성공과 실패를 구분할 수 없다.
    """
    if state == 'success':
        return QColor(38, 128, 74, 235), QColor(120, 220, 160), QColor(255, 255, 255)
    if state == 'failure':
        return QColor(150, 48, 48, 235), QColor(230, 130, 130), QColor(255, 255, 255)

    background = QColor(style.background_color)
    if not background.isValid():
        background = QColor(OVERLAY_FALLBACK_BACKGROUND)
    border = QColor(style.border_color)
    if not border.isValid():
        border = QColor(OVERLAY_FALLBACK_BORDER)
    text = QColor(style.text_color)
    if not text.isValid():
        text = QColor(OVERLAY_FALLBACK_TEXT)

    if state == 'hover':
        background = background.lighter(135)

    background.setAlpha(235)
    return background, border, text


def paint_dwell_gauge(painter: QPainter, rect: QRectF, outline_path: QPainterPath,
                      style, progress: float):
    """드웰 진행을 스타일이 정한 방법으로 그린다.

    진행이 보이지 않으면 사용자는 버튼이 반응하는지, 얼마나 더 기다려야 하는지
    알 수 없다. 드웰에서 진행 표시는 장식이 아니다.
    """
    if progress <= 0.0 or style.gauge == 'none':
        return

    progress = min(1.0, progress)
    color = QColor(style.gauge_color)
    if not color.isValid():
        color = QColor(OVERLAY_FALLBACK_GAUGE)

    if style.gauge == 'fill':
        # 왼쪽에서 오른쪽으로 차오른다. 버튼 모양 안쪽으로만 칠한다.
        painter.save()
        painter.setClipPath(outline_path)
        fill_color = QColor(color)
        fill_color.setAlpha(110)
        painter.fillRect(
            QRectF(rect.left(), rect.top(), rect.width() * progress, rect.height()),
            fill_color,
        )
        painter.restore()
        return

    if style.gauge == 'bar':
        # 버튼 아래쪽에 가로 막대.
        bar_height = max(3.0, min(8.0, rect.height() * 0.12))
        painter.save()
        painter.setClipPath(outline_path)
        painter.fillRect(
            QRectF(
                rect.left(),
                rect.bottom() - bar_height,
                rect.width() * progress,
                bar_height,
            ),
            color,
        )
        painter.restore()
        return

    # outline: 테두리를 따라 도는 선.
    pen = QPen(color, DWELL_RING_WIDTH)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)

    steps = max(2, int(progress * 120))
    trail = QPainterPath(outline_path.pointAtPercent(0.0))
    for index in range(1, steps + 1):
        trail.lineTo(outline_path.pointAtPercent(progress * index / steps))
    painter.drawPath(trail)


def paint_overlay_face(painter: QPainter, rect: QRectF, style, text: str,
                       state: str = 'idle', dwell_progress: float = 0.0) -> QPainterPath:
    """오버레이 버튼의 한 면을 그리고 외곽선 경로를 돌려준다.

    실제 버튼과 편집기 미리보기가 이 함수를 함께 쓴다. 미리보기가 실물과
    다르게 그려지면 사용자는 저장한 뒤에야 다르다는 것을 알게 된다.
    """
    painter.setRenderHint(QPainter.Antialiasing, True)

    path = build_overlay_path(rect, style.shape)
    background, border, text_color = resolve_overlay_colors(style, state)

    painter.fillPath(path, background)
    if style.border_width > 0:
        painter.setPen(QPen(border, style.border_width))
        painter.drawPath(path)

    paint_dwell_gauge(painter, rect, path, style, dwell_progress)

    font = QFont(painter.font())
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(text_color)

    inset = 12.0 if style.shape != 'circle' else rect.width() * 0.18
    text_rect = rect.adjusted(inset, 0.0, -inset, 0.0)
    metrics = QFontMetrics(font)
    elided = metrics.elidedText(text, Qt.ElideRight, max(10, int(text_rect.width())))
    painter.drawText(text_rect, Qt.AlignCenter, elided)

    return path


class OverlayButton(QWidget):
    """프로필 하나를 직전 활성 창에 적용하는 떠 있는 버튼."""

    # (성공 여부, 사용자에게 보여줄 메시지)
    profile_applied = pyqtSignal(bool, str)
    # 사용자가 이 버튼을 닫았다.
    closed = pyqtSignal(object)
    # 사용자가 이 버튼을 옮겼다. 배치를 저장할 시점이다.
    moved = pyqtSignal(object)

    def __init__(self, profile_id: str, profile_name: str, profile_manager,
                 foreground_tracker, parent=None, mode: str = MODE_CLICK,
                 dwell_ms: int = DEFAULT_DWELL_MS, style=None):
        super().__init__(parent)
        self.profile_id = profile_id
        self.profile_name = profile_name
        self.profile_manager = profile_manager
        self.foreground_tracker = foreground_tracker
        self._style = style if style is not None else _default_overlay_style()

        # 전역 설정. 프로필이 "전역 따름"일 때만 실제로 쓰인다.
        self._global_mode = mode
        self._global_dwell_ms = max(200, int(dwell_ms))
        # 잠그면 드래그로 옮길 수 없다. 드웰 중 실수로 끌려가는 것을 막는다.
        self._locked = False
        self._native_hwnd = 0

        self._drag_origin: Optional[QPoint] = None
        self._press_global: Optional[QPoint] = None
        self._dragged = False
        self._hovered = False
        self._feedback = None  # None, 'success', 'failure'

        # 드웰 상태. _dwell_armed가 False면 마우스가 한 번 나갔다 와야 다시 찬다.
        self._dwell_elapsed_ms = 0
        self._dwell_armed = True

        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.timeout.connect(self._clear_feedback)

        self._dwell_timer = QTimer(self)
        self._dwell_timer.setInterval(DWELL_TICK_MS)
        self._dwell_timer.timeout.connect(self._on_dwell_tick)

        self._setup_window()

    # -- 창 설정 -------------------------------------------------------

    def _setup_window(self):
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.resize(self._style.width, self._style.height)
        self._update_tooltip()

    # -- 생김새 -------------------------------------------------------

    @property
    def style_settings(self):
        return self._style

    def set_style(self, style):
        """프로필에서 바뀐 생김새를 반영한다. 위치는 그대로 둔다."""
        if style is None:
            return
        self._style = style
        self.resize(style.width, style.height)
        self._update_tooltip()
        self.update()

    def display_label(self) -> str:
        return self._style.resolved_label(self.profile_name)

    def _update_tooltip(self):
        if self.mode == MODE_DWELL:
            action = "마우스를 {0:.1f}초 올려두면".format(self.dwell_ms / 1000.0)
        else:
            action = "클릭하면"
        placement = (
            "위치가 잠겨 있습니다"
            if getattr(self, '_locked', False)
            else "드래그하면 위치를 옮길 수 있습니다"
        )
        self.setToolTip(
            "{0} 직전에 사용하던 창에 '{1}' 프로필을 적용합니다\n"
            "{2}".format(action, self.profile_name, placement)
        )

    # -- 발동 방식 -----------------------------------------------------

    @property
    def mode(self) -> str:
        """실제로 쓰이는 발동 방식. 프로필 설정이 전역 설정을 이긴다."""
        return self._style.resolved_activation(self._global_mode)

    @property
    def dwell_ms(self) -> int:
        """실제로 쓰이는 드웰 시간."""
        return self._style.resolved_dwell_ms(self._global_dwell_ms)

    def set_interaction_mode(self, mode: str):
        """전역 발동 방식을 바꾼다. 프로필이 따로 정했으면 그쪽이 우선한다."""
        if mode not in (MODE_CLICK, MODE_DWELL):
            logger.warning("알 수 없는 오버레이 발동 방식: %s", mode)
            return

        self._global_mode = mode
        self._cancel_dwell()
        self._update_tooltip()
        self.update()

    @property
    def locked(self) -> bool:
        return self._locked

    def set_locked(self, locked: bool):
        """위치 잠금을 켜고 끈다. 잠기면 드래그가 무시된다."""
        self._locked = bool(locked)
        self._update_tooltip()

    def set_dwell_duration(self, dwell_ms: int):
        """전역 드웰 시간을 바꾼다. 프로필이 따로 정했으면 그쪽이 우선한다."""
        self._global_dwell_ms = max(200, int(dwell_ms))
        self._cancel_dwell()
        self._update_tooltip()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        # 창을 닫은 뒤에는 winId를 물으면 안 된다. 그래서 여기서 기억해 둔다.
        self._native_hwnd = apply_no_activate_style(self)
        # 자기 자신은 절대 프로필 적용 대상이 되면 안 된다.
        if self.foreground_tracker is not None:
            self.foreground_tracker.exclude_hwnd(self._native_hwnd)

    @property
    def native_hwnd(self) -> int:
        """이 버튼의 창 핸들. 닫힌 뒤에도 안전하게 읽을 수 있다."""
        return self._native_hwnd

    # -- 마우스 -------------------------------------------------------

    def enterEvent(self, event):
        self._hovered = True
        if self.mode == MODE_DWELL and self._dwell_armed:
            self._start_dwell()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        # 마우스가 나가면 드웰이 다시 찬다. 한 번 머무름에 한 번만 발동한다.
        self._cancel_dwell()
        self._dwell_armed = True
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        # 배치하려고 누른 것이므로 드웰은 중단한다.
        self._cancel_dwell()
        if event.button() == Qt.LeftButton:
            self._press_global = event.globalPos()
            self._drag_origin = event.globalPos() - self.frameGeometry().topLeft()
            self._dragged = False
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._locked or self._drag_origin is None or not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return

        if not self._dragged and self._press_global is not None:
            moved = (event.globalPos() - self._press_global).manhattanLength()
            if moved < DRAG_THRESHOLD_PX:
                return
            self._dragged = True

        self.move(event.globalPos() - self._drag_origin)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            super().mouseReleaseEvent(event)
            return

        was_drag = self._dragged
        self._drag_origin = None
        self._press_global = None
        self._dragged = False

        if was_drag:
            self.moved.emit(self)
            # 배치를 마쳤다. 드웰 모드면 마우스가 아직 위에 있으니 다시 채워준다.
            if self.mode == MODE_DWELL and self._hovered and self._dwell_armed:
                self._start_dwell()
        elif self.mode == MODE_CLICK:
            self.trigger()
        event.accept()

    # -- 드웰 ---------------------------------------------------------

    def _start_dwell(self):
        self._dwell_elapsed_ms = 0
        if not self._dwell_timer.isActive():
            self._dwell_timer.start()

    def _cancel_dwell(self):
        if self._dwell_timer.isActive():
            self._dwell_timer.stop()
        self._dwell_elapsed_ms = 0
        self.update()

    def _on_dwell_tick(self):
        self._dwell_elapsed_ms += self._dwell_timer.interval()

        if self._dwell_elapsed_ms >= self.dwell_ms:
            self._dwell_timer.stop()
            self._dwell_elapsed_ms = 0
            # 마우스가 나갔다 들어오기 전까지 다시 발동하지 않는다.
            self._dwell_armed = False
            self.trigger()
            return

        self.update()

    def dwell_progress(self) -> float:
        """0.0에서 1.0 사이의 드웰 진행률."""
        if not self._dwell_timer.isActive() or self.dwell_ms <= 0:
            return 0.0
        return min(1.0, self._dwell_elapsed_ms / float(self.dwell_ms))

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        close_action = QAction("이 버튼 닫기", menu)
        close_action.triggered.connect(self._close_from_menu)
        menu.addAction(close_action)
        menu.exec_(event.globalPos())
        event.accept()

    def _close_from_menu(self):
        self.closed.emit(self)
        self.close()

    # -- 동작 ---------------------------------------------------------

    def trigger(self):
        """직전 활성 창에 프로필을 적용한다."""
        if self.foreground_tracker is None:
            self._finish(False, "창 추적기가 준비되지 않았습니다")
            return

        window_info = self.foreground_tracker.get_target_window_info()
        if not window_info:
            self._finish(False, "적용할 대상 창을 찾지 못했습니다")
            return

        title = window_info.get('title') or '제목 없는 창'
        try:
            success = self.profile_manager.apply_profile(self.profile_id, window_info)
        except Exception as exc:
            logger.error("오버레이 프로필 적용 중 오류: %s", exc)
            self._finish(False, "프로필 적용 실패: {0}".format(exc))
            return

        if success:
            self._finish(
                True,
                "'{0}' 프로필을 '{1}'에 적용했습니다".format(self.profile_name, title)
            )
        else:
            self._finish(False, "'{0}'에 프로필을 적용하지 못했습니다".format(title))

    def _finish(self, success: bool, message: str):
        self._feedback = 'success' if success else 'failure'
        self.update()
        self._feedback_timer.start(FEEDBACK_DURATION_MS)

        if success:
            logger.info(message)
        else:
            logger.warning(message)
        self.profile_applied.emit(success, message)

    def _clear_feedback(self):
        self._feedback = None
        self.update()

    # -- 그리기 -------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)

        margin = max(1.0, self._style.border_width)
        rect = QRectF(self.rect()).adjusted(margin, margin, -margin, -margin)

        paint_overlay_face(
            painter, rect, self._style, self.display_label(), self._paint_state(),
            self.dwell_progress()
        )

    def _paint_state(self) -> str:
        if self._feedback == 'success':
            return 'success'
        if self._feedback == 'failure':
            return 'failure'
        return 'hover' if self._hovered else 'idle'

