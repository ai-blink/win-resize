"""
Overlay Visibility Toggle Button
================================

오버레이 프로필 버튼을 한꺼번에 감추고 다시 꺼내는 작은 버튼이다.

존재 이유:
게임이나 영상처럼 화면을 가리면 안 되는 상황에서 프로필 버튼이 거슬린다고
버튼을 지워 버리면, 다시 쓰려면 본창을 열어 프로필마다 다시 켜야 한다.
그래서 배치는 그대로 두고 보이기만 끄는 스위치를 따로 둔다.

이 버튼은 자기 자신은 절대 숨지 않는다. 숨으면 다시 켤 방법이 없다.
"""

import logging
from typing import Optional

from PyQt5.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QAction, QMenu, QWidget

from gui.overlay_button import apply_no_activate_style

logger = logging.getLogger(__name__)

# 손으로 집기 편한 크기. 너무 작으면 옮기려다 눌리기만 한다.
DEFAULT_SIZE = 44

# 프로필 버튼보다 낮은 임계를 쓴다. 스위치는 작아서 끌기 시작한 것을
# 클릭으로 오해하기 쉽고, 그 오해의 대가가 "버튼이 전부 사라졌다"이다.
DRAG_THRESHOLD_PX = 3

# 눈 아이콘을 직접 그린다. 글꼴이나 특수 문자에 기대지 않으려는 선택이다.
ICON_BACKGROUND = "#262a34"
ICON_BACKGROUND_HIDDEN = "#4a3a22"
ICON_BORDER = "#6e7687"
ICON_FOREGROUND = "#e8ecf4"


class OverlayToggleButton(QWidget):
    """오버레이 버튼 전체를 보였다 감추는 작은 떠 있는 스위치."""

    # 사용자가 눌렀다. 인자는 "감춘 상태로 바꿔 달라"는 뜻이다.
    toggled_hidden = pyqtSignal(bool)
    # 사용자가 이 버튼을 옮겼다.
    moved = pyqtSignal(object)
    # 사용자가 이 버튼을 닫았다.
    closed = pyqtSignal(object)

    def __init__(self, foreground_tracker=None, parent=None, hidden: bool = False):
        super().__init__(parent)
        self.foreground_tracker = foreground_tracker

        self._hidden = bool(hidden)
        self._hovered = False
        self._locked = False
        self._native_hwnd = 0

        self._drag_origin: Optional[QPoint] = None
        self._press_global: Optional[QPoint] = None
        self._dragged = False

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
        self.setCursor(Qt.OpenHandCursor)
        self.resize(DEFAULT_SIZE, DEFAULT_SIZE)
        self._update_tooltip()

    # -- 상태 ---------------------------------------------------------

    @property
    def overlays_hidden(self) -> bool:
        return self._hidden

    def set_overlays_hidden(self, hidden: bool):
        """표시 상태를 반영한다. 시그널은 내보내지 않는다."""
        self._hidden = bool(hidden)
        self._update_tooltip()
        self.update()

    @property
    def locked(self) -> bool:
        return self._locked

    def set_locked(self, locked: bool):
        self._locked = bool(locked)
        self.setCursor(Qt.ArrowCursor if self._locked else Qt.OpenHandCursor)
        self._update_tooltip()

    @property
    def native_hwnd(self) -> int:
        return self._native_hwnd

    def _update_tooltip(self):
        action = "오버레이 버튼 다시 보기" if self._hidden else "오버레이 버튼 감추기"
        placement = "위치가 잠겨 있습니다" if self._locked else "드래그하면 옮길 수 있습니다"
        self.setToolTip("{0}\n{1}".format(action, placement))

    # -- 창 ----------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self._native_hwnd = apply_no_activate_style(self)
        if self.foreground_tracker is not None:
            self.foreground_tracker.exclude_hwnd(self._native_hwnd)

    # -- 마우스 -------------------------------------------------------

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_global = event.globalPos()
            self._drag_origin = event.globalPos() - self.frameGeometry().topLeft()
            self._dragged = False
            if not self._locked:
                self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._locked or self._drag_origin is None or not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return

        if not self._dragged and self._press_global is not None:
            if (event.globalPos() - self._press_global).manhattanLength() < DRAG_THRESHOLD_PX:
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
        self.setCursor(Qt.OpenHandCursor if not self._locked else Qt.ArrowCursor)

        if was_drag:
            self.moved.emit(self)
        else:
            self._hidden = not self._hidden
            self._update_tooltip()
            self.update()
            self.toggled_hidden.emit(self._hidden)

        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        close_action = QAction("이 스위치 닫기", menu)
        close_action.triggered.connect(self._close_from_menu)
        menu.addAction(close_action)
        menu.exec_(event.globalPos())
        event.accept()

    def _close_from_menu(self):
        self.closed.emit(self)
        self.close()

    # -- 그리기 -------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)

        background = QColor(ICON_BACKGROUND_HIDDEN if self._hidden else ICON_BACKGROUND)
        if self._hovered:
            background = background.lighter(135)
        background.setAlpha(235)

        path = QPainterPath()
        path.addEllipse(rect)
        painter.fillPath(path, background)
        painter.setPen(QPen(QColor(ICON_BORDER), 1.5))
        painter.drawPath(path)

        self._paint_eye(painter, rect)

    def _paint_eye(self, painter: QPainter, rect: QRectF):
        """눈 모양을 직접 그린다. 감춘 상태면 사선을 하나 긋는다."""
        pen = QPen(QColor(ICON_FOREGROUND), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)

        center = rect.center()
        eye_width = rect.width() * 0.56
        eye_height = rect.height() * 0.34

        eye = QPainterPath()
        eye.moveTo(center.x() - eye_width / 2, center.y())
        eye.quadTo(center.x(), center.y() - eye_height, center.x() + eye_width / 2, center.y())
        eye.quadTo(center.x(), center.y() + eye_height, center.x() - eye_width / 2, center.y())
        painter.drawPath(eye)

        pupil_radius = rect.width() * 0.10
        painter.setBrush(QColor(ICON_FOREGROUND))
        painter.drawEllipse(center, pupil_radius, pupil_radius)
        painter.setBrush(Qt.NoBrush)

        if self._hidden:
            slash_pen = QPen(QColor(ICON_FOREGROUND), 1.8)
            slash_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(slash_pen)
            offset = rect.width() * 0.30
            painter.drawLine(
                int(center.x() - offset), int(center.y() + offset),
                int(center.x() + offset), int(center.y() - offset),
            )
