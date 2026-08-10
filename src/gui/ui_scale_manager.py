"""Application-wide UI scale settings and helpers."""

import re
import weakref
from dataclasses import dataclass
from typing import Dict, List, Optional

from PyQt5.QtCore import QObject, QPoint, QSettings, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


DEFAULT_UI_SCALE_PERCENT = 90
MINIMUM_UI_SCALE_PERCENT = 75
MAXIMUM_UI_SCALE_PERCENT = 125
UI_SCALE_STEP_PERCENT = 5
_MAX_WIDGET_SIZE = 16777215
_STYLE_VALUE_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>px|pt)\b")


@dataclass
class _WidgetScaleState:
    """Original widget constraints retained for non-cumulative scaling."""

    widget_ref: object
    minimum_size: QSize
    maximum_size: QSize
    initial_size: QSize
    stylesheet: str


@dataclass
class _LayoutScaleState:
    """Original layout spacing retained for non-cumulative scaling."""

    layout_ref: object
    margins: object
    spacing: int


class UiScaleManager(QObject):
    """Own and apply the persisted visual scale for WindowResizer widgets."""

    scale_changed = pyqtSignal(int)

    def __init__(self, settings: Optional[QSettings] = None):
        super().__init__()
        self.settings = settings or QSettings("WindowResizer", "UiScale")
        self._scale_percent = self.normalize_scale(
            self.settings.value("scale_percent", DEFAULT_UI_SCALE_PERCENT)
        )
        self._base_application_font: Optional[QFont] = None
        self._window_states: Dict[int, List[_WidgetScaleState]] = {}
        self._layout_states: Dict[int, List[_LayoutScaleState]] = {}
        self._scale_root_geometry: Dict[int, bool] = {}

    @property
    def scale_percent(self) -> int:
        """Return the current scale as an integer percentage."""
        return self._scale_percent

    @property
    def factor(self) -> float:
        """Return the current scale multiplier."""
        return self._scale_percent / 100.0

    @staticmethod
    def normalize_scale(value) -> int:
        """Clamp a persisted or slider value to the supported scale steps."""
        try:
            numeric_value = int(float(value))
        except (TypeError, ValueError):
            numeric_value = DEFAULT_UI_SCALE_PERCENT

        numeric_value = max(MINIMUM_UI_SCALE_PERCENT, numeric_value)
        numeric_value = min(MAXIMUM_UI_SCALE_PERCENT, numeric_value)
        offset = numeric_value - MINIMUM_UI_SCALE_PERCENT
        rounded_offset = round(offset / UI_SCALE_STEP_PERCENT) * UI_SCALE_STEP_PERCENT
        return MINIMUM_UI_SCALE_PERCENT + rounded_offset

    def initialize_application(self) -> None:
        """Apply the saved value after QApplication exists and before UI creation."""
        app = QApplication.instance()
        if app is None:
            return

        if self._base_application_font is None:
            self._base_application_font = QFont(app.font())
        self._apply_application_font()

    def set_scale(self, value, persist: bool = True) -> int:
        """Apply a new scale, save it, and update registered widget trees."""
        new_scale = self.normalize_scale(value)
        changed = new_scale != self._scale_percent
        self._scale_percent = new_scale
        self.initialize_application()

        if persist:
            self.settings.setValue("scale_percent", self._scale_percent)
            sync = getattr(self.settings, "sync", None)
            if callable(sync):
                sync()

        self._apply_registered_windows()
        if changed:
            self.scale_changed.emit(self._scale_percent)
        return self._scale_percent

    def reset_to_default(self) -> int:
        """Restore the intentionally smaller default UI scale."""
        return self.set_scale(DEFAULT_UI_SCALE_PERCENT)

    def load_main_window_size(self) -> Optional[QSize]:
        """Return the last saved main window size when it is a valid QSize."""
        try:
            size = self.settings.value("main_window_size", None, type=QSize)
        except TypeError:
            size = self.settings.value("main_window_size", None)

        if isinstance(size, QSize) and size.width() > 0 and size.height() > 0:
            return QSize(size)
        return None

    def save_main_window_size(self, size: QSize) -> None:
        """Persist a valid main window size independently from UI scale."""
        if size.width() <= 0 or size.height() <= 0:
            return
        self.settings.setValue("main_window_size", QSize(size))
        sync = getattr(self.settings, "sync", None)
        if callable(sync):
            sync()

    def load_main_window_position(self) -> Optional[QPoint]:
        """Return the last saved main window position when it is valid."""
        try:
            position = self.settings.value("main_window_position", None, type=QPoint)
        except TypeError:
            position = self.settings.value("main_window_position", None)

        if isinstance(position, QPoint):
            return QPoint(position)
        return None

    def save_main_window_position(self, position: QPoint) -> None:
        """Persist the main window position independently from UI scale."""
        self.settings.setValue("main_window_position", QPoint(position))
        sync = getattr(self.settings, "sync", None)
        if callable(sync):
            sync()

    def scale_value(self, value: int, minimum: int = 0) -> int:
        """Scale one pixel value without allowing a positive value to disappear."""
        if value == 0:
            return 0
        scaled_value = int(round(value * self.factor))
        if value > 0:
            return max(minimum or 1, scaled_value)
        return min(-1, scaled_value)

    def scale_stylesheet(self, stylesheet: str) -> str:
        """Return a stylesheet with its explicit pixel and point sizes scaled."""
        if not stylesheet:
            return stylesheet

        def replace_value(match):
            value = float(match.group("value"))
            unit = match.group("unit")
            if unit == "px":
                scaled_value = self.scale_value(int(round(value)))
                return f"{scaled_value}px"

            scaled_value = value * self.factor
            text_value = f"{scaled_value:.2f}".rstrip("0").rstrip(".")
            return f"{text_value}pt"

        return _STYLE_VALUE_PATTERN.sub(replace_value, stylesheet)

    def register_window(self, window: QWidget, scale_root_geometry: bool = True) -> None:
        """Register a completed widget tree for future live scale changes."""
        window_id = id(window)
        self._window_states[window_id] = self._capture_widget_states(window)
        self._layout_states[window_id] = self._capture_layout_states(window)
        self._scale_root_geometry[window_id] = scale_root_geometry
        window.destroyed.connect(lambda *_args, key=window_id: self.unregister_window(key))
        self._apply_window_states(window_id)

    def unregister_window(self, window_or_id) -> None:
        """Forget a closed window or dialog without retaining a dead Qt wrapper."""
        window_id = window_or_id if isinstance(window_or_id, int) else id(window_or_id)
        self._window_states.pop(window_id, None)
        self._layout_states.pop(window_id, None)
        self._scale_root_geometry.pop(window_id, None)

    def refresh_stylesheet(self, window: QWidget) -> None:
        """Use newly generated theme CSS as the unscaled baseline for one root."""
        window_id = id(window)
        states = self._window_states.get(window_id)
        if not states:
            return

        for state in states:
            widget = state.widget_ref()
            if widget is not window:
                continue
            try:
                state.stylesheet = widget.styleSheet()
            except RuntimeError:
                continue
        self._apply_window_states(window_id, stylesheets_only=True)

    def _apply_application_font(self) -> None:
        app = QApplication.instance()
        if app is None or self._base_application_font is None:
            return

        scaled_font = QFont(self._base_application_font)
        if scaled_font.pointSizeF() > 0:
            scaled_font.setPointSizeF(self._base_application_font.pointSizeF() * self.factor)
        elif scaled_font.pixelSize() > 0:
            scaled_font.setPixelSize(self.scale_value(self._base_application_font.pixelSize()))
        app.setFont(scaled_font)

    def _capture_widget_states(self, window: QWidget) -> List[_WidgetScaleState]:
        widgets = [window, *window.findChildren(QWidget)]
        return [
            _WidgetScaleState(
                widget_ref=weakref.ref(widget),
                minimum_size=QSize(widget.minimumSize()),
                maximum_size=QSize(widget.maximumSize()),
                initial_size=QSize(widget.size()),
                stylesheet=widget.styleSheet(),
            )
            for widget in widgets
        ]

    def _capture_layout_states(self, window: QWidget) -> List[_LayoutScaleState]:
        layouts = []
        root_layout = window.layout()
        if root_layout is not None:
            layouts.append(root_layout)
        layouts.extend(window.findChildren(QLayout))

        unique_layouts = []
        seen_layout_ids = set()
        for layout in layouts:
            if id(layout) in seen_layout_ids:
                continue
            seen_layout_ids.add(id(layout))
            unique_layouts.append(layout)

        return [
            _LayoutScaleState(
                layout_ref=weakref.ref(layout),
                margins=layout.contentsMargins(),
                spacing=layout.spacing(),
            )
            for layout in unique_layouts
        ]

    def _apply_registered_windows(self) -> None:
        for window_id in list(self._window_states):
            self._apply_window_states(window_id)

    def _apply_window_states(self, window_id: int, stylesheets_only: bool = False) -> None:
        states = self._window_states.get(window_id, [])
        root_widget = states[0].widget_ref() if states else None
        if root_widget is None:
            self.unregister_window(window_id)
            return

        for state in states:
            widget = state.widget_ref()
            if widget is None:
                continue
            try:
                if not stylesheets_only:
                    if widget is not root_widget or self._scale_root_geometry.get(window_id, True):
                        widget.setMinimumSize(self._scale_size(state.minimum_size))
                        widget.setMaximumSize(self._scale_maximum_size(state.maximum_size))
                        if widget is root_widget:
                            widget.resize(self._scale_size(state.initial_size))
                if state.stylesheet:
                    widget.setStyleSheet(self.scale_stylesheet(state.stylesheet))
                widget.updateGeometry()
            except RuntimeError:
                continue

        if stylesheets_only:
            return

        for state in self._layout_states.get(window_id, []):
            layout = state.layout_ref()
            if layout is None:
                continue
            try:
                margins = state.margins
                layout.setContentsMargins(
                    self.scale_value(margins.left()),
                    self.scale_value(margins.top()),
                    self.scale_value(margins.right()),
                    self.scale_value(margins.bottom()),
                )
                if state.spacing >= 0:
                    layout.setSpacing(self.scale_value(state.spacing))
            except RuntimeError:
                continue

    def _scale_size(self, size: QSize) -> QSize:
        return QSize(
            self.scale_value(size.width()),
            self.scale_value(size.height()),
        )

    def _scale_maximum_size(self, size: QSize) -> QSize:
        return QSize(
            size.width() if size.width() >= _MAX_WIDGET_SIZE else self.scale_value(size.width()),
            size.height() if size.height() >= _MAX_WIDGET_SIZE else self.scale_value(size.height()),
        )


class UiScaleSettingsDialog(QDialog):
    """Live UI scale slider with a persistent smaller default."""

    def __init__(self, scale_manager: UiScaleManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.scale_manager = scale_manager
        self.setWindowTitle("UI 크기")
        self.setModal(False)

        layout = QVBoxLayout(self)
        description = QLabel("화면 크기")
        layout.addWidget(description)

        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.value_label)

        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(MINIMUM_UI_SCALE_PERCENT, MAXIMUM_UI_SCALE_PERCENT)
        self.scale_slider.setSingleStep(UI_SCALE_STEP_PERCENT)
        self.scale_slider.setPageStep(UI_SCALE_STEP_PERCENT)
        self.scale_slider.setTickInterval(10)
        self.scale_slider.setTickPosition(QSlider.TicksBelow)
        self.scale_slider.setValue(self.scale_manager.scale_percent)
        self.scale_slider.valueChanged.connect(self._set_scale_from_slider)
        layout.addWidget(self.scale_slider)

        button_layout = QHBoxLayout()
        self.reset_button = QPushButton("기본값 90%")
        self.reset_button.clicked.connect(self._reset_scale)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        close_button = QPushButton("닫기")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        self.scale_manager.scale_changed.connect(self._update_scale_display)
        self._update_scale_display(self.scale_manager.scale_percent)
        self.adjustSize()

    def _set_scale_from_slider(self, value: int) -> None:
        self.scale_manager.set_scale(value)

    def _reset_scale(self) -> None:
        self.scale_manager.reset_to_default()

    def _update_scale_display(self, value: int) -> None:
        self.value_label.setText(f"{value}%")
        if self.scale_slider.value() != value:
            self.scale_slider.blockSignals(True)
            self.scale_slider.setValue(value)
            self.scale_slider.blockSignals(False)


default_ui_scale_manager: Optional[UiScaleManager] = None


def get_ui_scale_manager() -> UiScaleManager:
    """Return the process-wide UI scale manager."""
    global default_ui_scale_manager
    if default_ui_scale_manager is None:
        default_ui_scale_manager = UiScaleManager()
    return default_ui_scale_manager
