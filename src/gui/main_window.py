"""
Main Window GUI for WindowResizer
=================================

PyQt5-based main application window with window list, coordinate controls,
and integration with Phase 1 Windows API functionality.

Key Features:
- Window list with real-time updates
- Coordinate input controls (X, Y, Width, Height)
- Apply/Save/Center button actions
- Real-time coordinate display
- Integration with enhanced window manipulator
- Error handling and user feedback
"""

import sys
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QListWidget, QListWidgetItem, QSpinBox, QLabel, QPushButton,
    QGroupBox, QStatusBar, QMenuBar, QAction, QMessageBox,
    QProgressBar, QCheckBox, QComboBox, QLineEdit, QSplitter,
    QFrame, QApplication, QTableWidget, QTableWidgetItem, QDoubleSpinBox,
    QSizePolicy, QSystemTrayIcon, QMenu, QStyle
)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal, QSize, QPoint, QRect
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor

# Import Phase 1 components
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.enhanced_window_manipulator import EnhancedWindowManipulator
from core.window_enumerator import WindowEnumerator, FilterMode
from core.windows_api import WindowRect

# Import Phase 3 components
from core.profile_manager import default_profile_manager
from gui.profile_dialog import ProfileManagerDialog, ProfileEditDialog

# Import Phase 6 components
from gui.theme_manager import get_theme_manager, ThemeElement, ThemeType
from gui.profile_editor import ProfileEditorDialog
from gui.preset_controls import PresetControlsWidget

logger = logging.getLogger(__name__)

@dataclass
class WindowInfo:
    """Window information for GUI display."""
    hwnd: int
    title: str
    rect: WindowRect
    process_name: str = "Unknown"
    pid: int = 0
    executable_path: str = ""
    is_visible: bool = True
    is_minimized: bool = False
    is_maximized: bool = False

class ProfilePreviewOverlay(QWidget):
    """Show the stored profile geometry without changing the target window."""

    def __init__(self, profile, theme_manager):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowOpacity(0.72)

        config = profile.window_config
        screens = QApplication.screens()
        self.setGeometry(
            self.native_geometry_to_qt_geometry(
                config, screens, self.native_screen_geometries(screens)
            )
        )

        accent = theme_manager.get_color_string(ThemeElement.ACCENT)
        foreground = theme_manager.get_color_string(ThemeElement.FOREGROUND)
        text = theme_manager.get_color_string(ThemeElement.TEXT)
        self.setStyleSheet(
            f"QWidget {{ background-color: {foreground}; border: 3px dashed {accent}; }}"
            f"QLabel {{ color: {text}; background: transparent; font-weight: bold; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        label = QLabel(
            f"{profile.name}\n{config.x}, {config.y} / {config.width} x {config.height}"
        )
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        layout.addWidget(label)

    @staticmethod
    def native_screen_geometries(screens):
        """Return Win32 physical monitor rectangles in the Qt screen order."""
        monitor_bounds = {}
        try:
            import win32api

            for monitor, _, _ in win32api.EnumDisplayMonitors():
                monitor_info = win32api.GetMonitorInfo(monitor)
                device_name = monitor_info.get("Device", "").casefold()
                monitor_bounds[device_name] = QRect(*monitor_info["Monitor"][:2],
                                                    monitor_info["Monitor"][2] - monitor_info["Monitor"][0],
                                                    monitor_info["Monitor"][3] - monitor_info["Monitor"][1])
        except Exception as error:
            logger.debug(f"Could not read native monitor geometry: {error}")

        native_geometries = []
        for screen in screens:
            screen_name = screen.name().casefold()
            matching_geometry = next(
                (bounds for device, bounds in monitor_bounds.items()
                 if device.endswith(screen_name)),
                None,
            )
            if matching_geometry is None:
                geometry = screen.geometry()
                scale_factor = screen.devicePixelRatio()
                matching_geometry = QRect(
                    round(geometry.x() * scale_factor),
                    round(geometry.y() * scale_factor),
                    round(geometry.width() * scale_factor),
                    round(geometry.height() * scale_factor),
                )
            native_geometries.append(matching_geometry)
        return native_geometries

    @staticmethod
    def native_geometry_to_qt_geometry(config, screens, native_geometries=None) -> QRect:
        """Convert a Win32 physical rectangle to the matching Qt screen geometry."""
        if native_geometries is None:
            native_geometries = []
            for screen in screens:
                geometry = screen.geometry()
                scale_factor = screen.devicePixelRatio()
                native_geometries.append(QRect(
                    round(geometry.x() * scale_factor),
                    round(geometry.y() * scale_factor),
                    round(geometry.width() * scale_factor),
                    round(geometry.height() * scale_factor),
                ))

        fallback_screen = screens[0] if screens else None
        fallback_native_geometry = native_geometries[0] if native_geometries else None
        for screen, native_geometry in zip(screens, native_geometries):
            if native_geometry.contains(QPoint(config.x, config.y)):
                fallback_screen = screen
                fallback_native_geometry = native_geometry
                break

        if fallback_screen is None or fallback_native_geometry is None:
            return QRect(config.x, config.y, config.width, config.height)

        geometry = fallback_screen.geometry()
        scale_factor = fallback_screen.devicePixelRatio()
        return QRect(
            geometry.x() + round((config.x - fallback_native_geometry.x()) / scale_factor),
            geometry.y() + round((config.y - fallback_native_geometry.y()) / scale_factor),
            max(1, round(config.width / scale_factor)),
            max(1, round(config.height / scale_factor)),
        )


class WindowUpdateThread(QThread):
    """Background thread for updating window list."""
    windows_updated = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.enumerator = WindowEnumerator()
        self.running = True
    
    def run(self):
        """Update window list in background."""
        try:
            windows = self.enumerator.enumerate_windows(
                FilterMode.USER_WINDOWS, 
                include_process_info=True
            )
            
            window_infos = []
            for window in windows:
                if window.title.strip():  # Only include windows with titles
                    window_info = WindowInfo(
                        hwnd=window.hwnd,
                        title=window.title,
                        rect=window.rect,
                        process_name=window.process_info.name if window.process_info else "Unknown",
                        pid=window.process_info.pid if window.process_info else 0,
                        executable_path=window.process_info.exe_path if window.process_info else "",
                        is_visible=window.is_visible,
                        is_minimized=window.is_minimized,
                        is_maximized=window.is_maximized
                    )
                    window_infos.append(window_info)
            
            self.windows_updated.emit(window_infos)
            
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def stop(self):
        """Stop the update thread."""
        self.running = False

class WindowResizerMainWindow(QMainWindow):
    """Main application window for WindowResizer."""

    auto_profile_applied_signal = pyqtSignal(int, object)
    monitor_error_signal = pyqtSignal(str, object)

    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        
        # Initialize Phase 1 components
        self.window_manipulator = EnhancedWindowManipulator()
        self.enumerator = WindowEnumerator()
        
        # Initialize Phase 3 components first (needed by Phase 2)
        self.profile_manager = default_profile_manager
        self.profile_manager_dialog = None
        
        # Initialize Phase 2 - Auto-apply system
        from core.window_monitor import WindowMonitor, MonitoringConfig
        self.monitor_config = MonitoringConfig()
        self.window_monitor = WindowMonitor(self.profile_manager, self.monitor_config)
        self.auto_profile_applied_signal.connect(self.on_profile_auto_applied)
        self.monitor_error_signal.connect(self.on_monitor_error)
        self.window_monitor.set_profile_applied_callback(self._queue_profile_auto_applied)
        self.window_monitor.set_error_callback(self._queue_monitor_error)
        
        # Initialize Phase 6 components
        self.theme_manager = get_theme_manager()
        self.preset_controls = None
        
        # Window state
        self.current_window: Optional[WindowInfo] = None
        self.window_list: List[WindowInfo] = []
        self.debug_window = None  # 디버그 창 인스턴스
        self.profile_preview_overlay = None
        self.tray_icon = None
        self.tray_menu = None
        self._quit_requested = False
        self._tray_notification_shown = False
        
        # Threading
        self.update_thread = None
        
        # Setup GUI
        self.setup_ui()
        self.setup_timers()
        self.setup_connections()
        self.setup_system_tray()
        
        # Initial window list update
        self.refresh_window_list()
        
        # Initialize profile list (only if profile_combo exists)
        if hasattr(self, 'profile_combo'):
            self.refresh_profile_list()
        
        logger.info("WindowResizerMainWindow initialized")
    
    def show_themed_information(self, title, message):
        """Show information message with completely custom dark dialog."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PyQt5.QtCore import Qt
        
        theme_manager = get_theme_manager()
        current_theme = theme_manager.current_theme
        
        if current_theme == ThemeType.DARK:
            # Create completely custom dialog
            dialog = QDialog(self)
            dialog.setWindowTitle(title)
            dialog.setModal(True)
            dialog.resize(450, 200)
            dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            
            # Main layout
            layout = QVBoxLayout(dialog)
            layout.setSpacing(20)
            layout.setContentsMargins(30, 30, 30, 30)
            
            # Content layout (icon + text)
            content_layout = QHBoxLayout()
            
            # Information icon
            icon_label = QLabel("ℹ️")
            icon_label.setStyleSheet("""
                QLabel {
                    color: #4dabf7;
                    font-size: 24pt;
                    font-weight: bold;
                    padding: 10px;
                    background-color: transparent;
                }
            """)
            content_layout.addWidget(icon_label)
            
            # Message text
            message_label = QLabel(message)
            message_label.setWordWrap(True)
            message_label.setStyleSheet("""
                QLabel {
                    color: #ffffff;
                    font-size: 13pt;
                    font-weight: normal;
                    padding: 10px;
                    background-color: transparent;
                    border: none;
                    line-height: 1.4;
                }
            """)
            content_layout.addWidget(message_label)
            
            layout.addLayout(content_layout)
            
            # Button layout
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            ok_button = QPushButton("확인")
            ok_button.setStyleSheet("""
                QPushButton {
                    background-color: #0078d4;
                    color: #ffffff;
                    border: 2px solid #0078d4;
                    border-radius: 6px;
                    padding: 12px 30px;
                    font-weight: bold;
                    font-size: 12pt;
                    min-width: 80px;
                    min-height: 35px;
                }
                QPushButton:hover {
                    background-color: #106ebe;
                    border: 2px solid #ffffff;
                }
                QPushButton:pressed {
                    background-color: #005a9e;
                }
            """)
            
            button_layout.addWidget(ok_button)
            layout.addLayout(button_layout)
            
            # Dialog styling - FORCE dark background
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b !important;
                    border: 2px solid #4dabf7;
                    border-radius: 8px;
                }
            """)
            
            # Connect button
            ok_button.clicked.connect(dialog.accept)
            ok_button.setDefault(True)
            
            # Execute dialog
            return dialog.exec_()
            
        else:
            # Use standard message box for light mode
            from PyQt5.QtWidgets import QMessageBox
            return QMessageBox.information(self, title, message)
    
    def show_themed_warning(self, title, message):
        """Show warning message with completely custom dark dialog."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QIcon, QPixmap, QPainter
        
        theme_manager = get_theme_manager()
        current_theme = theme_manager.current_theme
        
        if current_theme == ThemeType.DARK:
            # Create completely custom dialog
            dialog = QDialog(self)
            dialog.setWindowTitle(title)
            dialog.setModal(True)
            dialog.resize(450, 200)
            dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            
            # Main layout
            layout = QVBoxLayout(dialog)
            layout.setSpacing(20)
            layout.setContentsMargins(30, 30, 30, 30)
            
            # Content layout (icon + text)
            content_layout = QHBoxLayout()
            
            # Warning icon (create simple text icon)
            icon_label = QLabel("⚠️")
            icon_label.setStyleSheet("""
                QLabel {
                    color: #ffcc00;
                    font-size: 24pt;
                    font-weight: bold;
                    padding: 10px;
                    background-color: transparent;
                }
            """)
            content_layout.addWidget(icon_label)
            
            # Message text
            message_label = QLabel(message)
            message_label.setWordWrap(True)
            message_label.setStyleSheet("""
                QLabel {
                    color: #ffffff;
                    font-size: 13pt;
                    font-weight: normal;
                    padding: 10px;
                    background-color: transparent;
                    border: none;
                    line-height: 1.4;
                }
            """)
            content_layout.addWidget(message_label)
            
            layout.addLayout(content_layout)
            
            # Button layout
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            ok_button = QPushButton("확인")
            ok_button.setStyleSheet("""
                QPushButton {
                    background-color: #0078d4;
                    color: #ffffff;
                    border: 2px solid #0078d4;
                    border-radius: 6px;
                    padding: 12px 30px;
                    font-weight: bold;
                    font-size: 12pt;
                    min-width: 80px;
                    min-height: 35px;
                }
                QPushButton:hover {
                    background-color: #106ebe;
                    border: 2px solid #ffffff;
                }
                QPushButton:pressed {
                    background-color: #005a9e;
                }
            """)
            
            button_layout.addWidget(ok_button)
            layout.addLayout(button_layout)
            
            # Dialog styling - FORCE dark background
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b !important;
                    border: 2px solid #555555;
                    border-radius: 8px;
                }
            """)
            
            # Connect button
            ok_button.clicked.connect(dialog.accept)
            ok_button.setDefault(True)
            
            # Execute dialog
            return dialog.exec_()
            
        else:
            # Use standard message box for light mode
            from PyQt5.QtWidgets import QMessageBox
            return QMessageBox.warning(self, title, message)
    
    def show_themed_critical(self, title, message):
        """Show critical error message with completely custom dark dialog."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PyQt5.QtCore import Qt
        
        theme_manager = get_theme_manager()
        current_theme = theme_manager.current_theme
        
        if current_theme == ThemeType.DARK:
            # Create completely custom dialog
            dialog = QDialog(self)
            dialog.setWindowTitle(title)
            dialog.setModal(True)
            dialog.resize(450, 200)
            dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            
            # Main layout
            layout = QVBoxLayout(dialog)
            layout.setSpacing(20)
            layout.setContentsMargins(30, 30, 30, 30)
            
            # Content layout (icon + text)
            content_layout = QHBoxLayout()
            
            # Error icon
            icon_label = QLabel("❌")
            icon_label.setStyleSheet("""
                QLabel {
                    color: #ff4444;
                    font-size: 24pt;
                    font-weight: bold;
                    padding: 10px;
                    background-color: transparent;
                }
            """)
            content_layout.addWidget(icon_label)
            
            # Message text
            message_label = QLabel(message)
            message_label.setWordWrap(True)
            message_label.setStyleSheet("""
                QLabel {
                    color: #ffffff;
                    font-size: 13pt;
                    font-weight: normal;
                    padding: 10px;
                    background-color: transparent;
                    border: none;
                    line-height: 1.4;
                }
            """)
            content_layout.addWidget(message_label)
            
            layout.addLayout(content_layout)
            
            # Button layout
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            ok_button = QPushButton("확인")
            ok_button.setStyleSheet("""
                QPushButton {
                    background-color: #d13438;
                    color: #ffffff;
                    border: 2px solid #d13438;
                    border-radius: 6px;
                    padding: 12px 30px;
                    font-weight: bold;
                    font-size: 12pt;
                    min-width: 80px;
                    min-height: 35px;
                }
                QPushButton:hover {
                    background-color: #a02328;
                    border: 2px solid #ffffff;
                }
                QPushButton:pressed {
                    background-color: #801b1f;
                }
            """)
            
            button_layout.addWidget(ok_button)
            layout.addLayout(button_layout)
            
            # Dialog styling - FORCE dark background
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b !important;
                    border: 2px solid #d13438;
                    border-radius: 8px;
                }
            """)
            
            # Connect button
            ok_button.clicked.connect(dialog.accept)
            ok_button.setDefault(True)
            
            # Execute dialog
            return dialog.exec_()
            
        else:
            # Use standard message box for light mode
            from PyQt5.QtWidgets import QMessageBox
            return QMessageBox.critical(self, title, message)
    
    def show_themed_input_dialog(self, title, label, default_text=""):
        """Show input dialog with strong dark mode theme styling."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
        
        theme_manager = get_theme_manager()
        current_theme = theme_manager.current_theme
        
        if current_theme == ThemeType.DARK:
            # Create custom dialog for better dark mode control
            dialog = QDialog(self)
            dialog.setWindowTitle(title)
            dialog.setModal(True)
            dialog.resize(400, 150)
            
            # Main layout
            layout = QVBoxLayout(dialog)
            layout.setSpacing(15)
            layout.setContentsMargins(20, 20, 20, 20)
            
            # Label
            label_widget = QLabel(label)
            label_widget.setStyleSheet("""
                QLabel {
                    color: #ffffff;
                    font-size: 13pt;
                    font-weight: normal;
                    padding: 5px;
                    border: none;
                    background-color: transparent;
                }
            """)
            layout.addWidget(label_widget)
            
            # Input field
            input_field = QLineEdit(default_text)
            input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #3c3c3c;
                    color: #ffffff;
                    border: 2px solid #666666;
                    border-radius: 4px;
                    padding: 10px;
                    font-size: 12pt;
                    min-height: 25px;
                }
                QLineEdit:focus {
                    border: 2px solid #0078d4;
                    background-color: #404040;
                }
            """)
            layout.addWidget(input_field)
            
            # Buttons
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            ok_button = QPushButton("확인")
            ok_button.setStyleSheet("""
                QPushButton {
                    background-color: #0078d4;
                    color: #ffffff;
                    border: 2px solid #0078d4;
                    border-radius: 6px;
                    padding: 12px 24px;
                    font-weight: bold;
                    font-size: 11pt;
                    min-width: 80px;
                    min-height: 30px;
                }
                QPushButton:hover {
                    background-color: #106ebe;
                    border: 2px solid #ffffff;
                }
                QPushButton:pressed {
                    background-color: #005a9e;
                }
            """)
            
            cancel_button = QPushButton("취소")
            cancel_button.setStyleSheet("""
                QPushButton {
                    background-color: #3c3c3c;
                    border: 2px solid #666666;
                    border-radius: 6px;
                    padding: 12px 24px;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 11pt;
                    min-width: 80px;
                    min-height: 30px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                    border: 2px solid #0078d4;
                }
                QPushButton:pressed {
                    background-color: #5a5a5a;
                }
            """)
            
            button_layout.addWidget(cancel_button)
            button_layout.addWidget(ok_button)
            layout.addLayout(button_layout)
            
            # Dialog styling
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b;
                    border: 2px solid #555555;
                    border-radius: 8px;
                }
            """)
            
            # Connect buttons
            ok_pressed = False
            def on_ok():
                nonlocal ok_pressed
                ok_pressed = True
                dialog.accept()
            
            def on_cancel():
                dialog.reject()
            
            ok_button.clicked.connect(on_ok)
            cancel_button.clicked.connect(on_cancel)
            ok_button.setDefault(True)
            
            # Focus on input field
            input_field.setFocus()
            input_field.selectAll()
            
            # Execute dialog
            result = dialog.exec_()
            text = input_field.text()
            return text, result == QDialog.Accepted
            
        else:
            # Use standard input dialog for light mode
            from PyQt5.QtWidgets import QInputDialog
            return QInputDialog.getText(self, title, label, text=default_text)
    
    def setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle("창모드 리사이저 0.01.4")
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(15)
        
        # === ORIGINAL LAYOUT CODE (COMMENTED FOR BACKUP) ===
        # panels_widget = QWidget()
        # panels_layout = QVBoxLayout(panels_widget)
        # panels_layout.setContentsMargins(0, 0, 0, 0)
        # panels_layout.setSpacing(5)
        # main_layout.addWidget(panels_widget)
        # top_panel_widget = QWidget()
        # top_panel_layout = QVBoxLayout(top_panel_widget)
        # self.create_window_list_panel(top_panel_widget)
        # panels_layout.addWidget(top_panel_widget)
        # profile_group = self.create_profile_panel_direct()
        # panels_layout.addWidget(profile_group)
        # controls_panel_widget = QWidget()
        # self.create_controls_panel(controls_panel_layout)
        # panels_layout.addWidget(controls_panel_widget)
        # panels_layout.setStretch(0, 5); panels_layout.setStretch(1, 5); panels_layout.setStretch(2, 2)
        
        # === NEW REDESIGNED LAYOUT SYSTEM ===
        # Using QGridLayout for absolute control over space distribution
        main_grid = QGridLayout()
        main_grid.setContentsMargins(5, 5, 5, 5)
        main_grid.setSpacing(5)
        
        # Row 0: Window list (40% height)
        self.window_section = QWidget()
        self.window_section.setMinimumHeight(340)
        self.window_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        window_section_layout = QVBoxLayout(self.window_section)
        window_section_layout.setContentsMargins(0, 0, 0, 0)
        self.create_window_list_panel(self.window_section)
        main_grid.addWidget(self.window_section, 0, 0)
        
        # Row 1: Profile list (40% height)
        self.profile_section = QWidget()
        self.profile_section.setMinimumHeight(280)
        self.profile_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        profile_section_layout = QVBoxLayout(self.profile_section)
        profile_section_layout.setContentsMargins(0, 0, 0, 0)
        profile_section_layout.setSpacing(0)
        # Create new streamlined profile panel
        profile_group = self.create_profile_panel_redesigned()
        profile_section_layout.addWidget(profile_group)
        main_grid.addWidget(self.profile_section, 1, 0)
        
        # Row 2: Controls (hidden - not needed)
        self.controls_section = QWidget()
        self.controls_section.setMinimumHeight(0)   # Hide controls section
        self.controls_section.setMaximumHeight(0)   # Hide controls section  
        self.controls_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        controls_section_layout = QVBoxLayout(self.controls_section)
        controls_section_layout.setContentsMargins(0, 0, 0, 0)
        self.create_controls_panel(controls_section_layout)
        main_grid.addWidget(self.controls_section, 2, 0)
        
        # Set precise row stretch ratios: 1:1:0 (50:50:0)
        main_grid.setRowStretch(0, 1)  # Window list - 50%
        main_grid.setRowStretch(1, 1)  # Profile list - 50% 
        main_grid.setRowStretch(2, 0)  # Controls - hidden (0%)
        
        # Apply grid layout to main layout
        grid_container = QWidget()
        grid_container.setLayout(main_grid)
        main_layout.addWidget(grid_container)
        
        # Setup menu bar
        self.setup_menu_bar()
        
        # Setup status bar
        self.setup_status_bar()
        
        # Set window size constraints to prevent excessive empty space
        self.setup_window_constraints()
        
        # Apply styling
        self.apply_styling()
        
        # Apply theme styling
        self.apply_theme_styling()
    
    def create_window_list_panel(self, parent):
        """Create the window list panel."""
        # Create window list group
        window_group = QGroupBox("활성 창 목록")
        window_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Removed maximum height to allow stretch factor to work properly
        window_layout = QVBoxLayout(window_group)
        
        # Create refresh controls and search bar
        refresh_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.setToolTip("창 목록을 새로고침합니다")
        refresh_layout.addWidget(self.refresh_button)
        
        self.auto_refresh_checkbox = QCheckBox("자동 새로고침")
        self.auto_refresh_checkbox.setChecked(False)  # 기본적으로 비활성화
        self.auto_refresh_checkbox.setToolTip("창 목록을 5초마다 자동으로 새로고침")
        refresh_layout.addWidget(self.auto_refresh_checkbox)
        
        # Add search bar next to refresh controls
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("창 검색...")
        self.search_input.setMaximumWidth(200)
        refresh_layout.addWidget(self.search_input)
        
        self.search_button = QPushButton("검색")
        self.search_button.setToolTip("입력된 텍스트로 창을 검색합니다")
        refresh_layout.addWidget(self.search_button)
        
        # Add theme toggle button with blue styling
        self.theme_toggle_button = QPushButton()
        self.theme_toggle_button.setFixedSize(32, 32)
        self.theme_toggle_button.setToolTip("다크/라이트 테마 전환")
        self.theme_toggle_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: 1px solid #0056b3;
                border-radius: 16px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
                border-color: #004085;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        self.update_theme_button_icon()
        refresh_layout.addWidget(self.theme_toggle_button)
        
        # Theme toggle description label
        self.theme_description_label = QLabel("테마")
        self.theme_description_label.setToolTip("다크/라이트 테마 전환 버튼")
        refresh_layout.addWidget(self.theme_description_label)
        
        refresh_layout.addStretch()
        
        self.window_count_label = QLabel("창 0개")
        refresh_layout.addWidget(self.window_count_label)
        
        window_layout.addLayout(refresh_layout)
        
        # Create window list table
        self.window_list_widget = QTableWidget()
        self.window_list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.window_list_widget.setMinimumHeight(280)  # 적절한 최소 높이 설정
        # Removed maximum height to allow table to expand with stretch factor
        self.window_list_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.window_list_widget.setSelectionMode(QTableWidget.SingleSelection)
        self.window_list_widget.setAlternatingRowColors(True)
        self.window_list_widget.setEditTriggers(QTableWidget.NoEditTriggers)  # 편집 불가
        
        # Set up table headers - Add PID column and expand window name
        headers = ["창 이름", "PID", "프로세스", "X", "Y", "폭", "높이"]
        self.window_list_widget.setColumnCount(len(headers))
        self.window_list_widget.setHorizontalHeaderLabels(headers)
        
        # Configure column widths with responsive design
        header = self.window_list_widget.horizontalHeader()
        header.setDefaultSectionSize(80)
        
        # Set fixed column widths for coordinates and expanding columns for name/process
        self.window_list_widget.setColumnWidth(0, 300)  # 창 이름 - will be resizable
        self.window_list_widget.setColumnWidth(1, 80)   # PID - fixed
        self.window_list_widget.setColumnWidth(2, 200)  # 프로세스 - will be resizable  
        self.window_list_widget.setColumnWidth(3, 80)   # X - fixed
        self.window_list_widget.setColumnWidth(4, 80)   # Y - fixed  
        self.window_list_widget.setColumnWidth(5, 80)   # 폭 - fixed
        self.window_list_widget.setColumnWidth(6, 80)   # 높이 - fixed (same as other coordinates)
        
        # Set resize modes - only name and process columns can expand
        header.setSectionResizeMode(0, header.Stretch)      # 창 이름 - expandable
        header.setSectionResizeMode(1, header.Fixed)        # PID - fixed
        header.setSectionResizeMode(2, header.Stretch)      # 프로세스 - expandable
        header.setSectionResizeMode(3, header.Fixed)        # X - fixed
        header.setSectionResizeMode(4, header.Fixed)        # Y - fixed
        header.setSectionResizeMode(5, header.Fixed)        # 폭 - fixed
        header.setSectionResizeMode(6, header.Fixed)        # 높이 - fixed
        
        # Enable sorting
        self.window_list_widget.setSortingEnabled(True)
        
        window_layout.addWidget(self.window_list_widget)
        
        parent.layout().addWidget(window_group)
        
        # Create coordinate controls panel (moved from below)
        coords_group = QGroupBox("창 크기 및 위치 조정")
        # Removed maximum height to allow group to expand
        coords_group_layout = QVBoxLayout(coords_group)
        
        # Current window info
        current_window_layout = QHBoxLayout()
        current_window_layout.addWidget(QLabel("선택된 창:"))
        
        self.current_window_label = QLabel("선택하지 않음")
        self.current_window_label.setStyleSheet("font-weight: bold;")
        current_window_layout.addWidget(self.current_window_label)
        current_window_layout.addStretch()
        
        coords_group_layout.addLayout(current_window_layout)
        
        # Coordinate controls with tight label-spinbox pairs
        coord_controls_layout = QHBoxLayout()
        coord_controls_layout.setSpacing(120)
        coord_controls_layout.setAlignment(Qt.AlignLeft)
        
        # X coordinate - label and spinbox very close together
        x_container = QHBoxLayout()
        x_container.setContentsMargins(0, 0, 0, 0)
        x_container.setSpacing(2)
        x_label = QLabel("X:")
        x_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        x_container.addWidget(x_label)
        self.x_spinbox = QSpinBox()
        self.x_spinbox.setRange(-9999, 9999)
        self.x_spinbox.setSuffix(" px")
        self.x_spinbox.setToolTip("창의 X 좌표 (가로 위치)")
        x_container.addWidget(self.x_spinbox)
        coord_controls_layout.addLayout(x_container)
        
        # Y coordinate - label and spinbox very close together
        y_container = QHBoxLayout()
        y_container.setContentsMargins(0, 0, 0, 0)
        y_container.setSpacing(2)
        y_label = QLabel("Y:")
        y_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        y_container.addWidget(y_label)
        self.y_spinbox = QSpinBox()
        self.y_spinbox.setRange(-9999, 9999)
        self.y_spinbox.setSuffix(" px")
        self.y_spinbox.setToolTip("창의 Y 좌표 (세로 위치)")
        y_container.addWidget(self.y_spinbox)
        coord_controls_layout.addLayout(y_container)
        
        # Width - label and spinbox very close together
        width_container = QHBoxLayout()
        width_container.setContentsMargins(0, 0, 0, 0)
        width_container.setSpacing(2)
        width_label = QLabel("폭:")
        width_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        width_container.addWidget(width_label)
        self.width_spinbox = QSpinBox()
        self.width_spinbox.setRange(1, 9999)
        self.width_spinbox.setSuffix(" px")
        self.width_spinbox.setToolTip("창의 너비")
        width_container.addWidget(self.width_spinbox)
        coord_controls_layout.addLayout(width_container)
        
        # Height - label and spinbox very close together
        height_container = QHBoxLayout()
        height_container.setContentsMargins(0, 0, 0, 0)
        height_container.setSpacing(2)
        height_label = QLabel("높이:")
        height_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        height_container.addWidget(height_label)
        self.height_spinbox = QSpinBox()
        self.height_spinbox.setRange(1, 9999)
        self.height_spinbox.setSuffix(" px")
        self.height_spinbox.setToolTip("창의 높이")
        height_container.addWidget(self.height_spinbox)
        coord_controls_layout.addLayout(height_container)
        
        coords_group_layout.addLayout(coord_controls_layout)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.get_coords_button = QPushButton("현재 좌표 가져오기")
        self.get_coords_button.setToolTip("선택된 창의 현재 위치와 크기를 가져옵니다")
        self.get_coords_button.setEnabled(False)
        button_layout.addWidget(self.get_coords_button)
        
        self.apply_button = QPushButton("적용")
        self.apply_button.setToolTip("입력된 좌표와 크기를 창에 적용합니다")
        self.apply_button.setEnabled(False)
        button_layout.addWidget(self.apply_button)
        
        # Position presets - reordered: 위, 아래, 화면 중앙, 왼쪽, 오른쪽
        self.pos_up_button = QPushButton("위")
        self.pos_up_button.setToolTip("창을 화면 상단으로 이동")
        self.pos_up_button.setEnabled(True)
        button_layout.addWidget(self.pos_up_button)
        
        self.pos_down_button = QPushButton("아래")
        self.pos_down_button.setToolTip("창을 화면 하단으로 이동")
        self.pos_down_button.setEnabled(True)
        button_layout.addWidget(self.pos_down_button)
        
        self.center_button = QPushButton("화면 중앙")
        self.center_button.setToolTip("창을 화면 중앙으로 이동합니다")
        self.center_button.setEnabled(True)
        button_layout.addWidget(self.center_button)
        
        self.pos_left_button = QPushButton("왼쪽")
        self.pos_left_button.setToolTip("창을 화면 왼쪽으로 이동")
        self.pos_left_button.setEnabled(True)
        button_layout.addWidget(self.pos_left_button)
        
        self.pos_right_button = QPushButton("오른쪽")
        self.pos_right_button.setToolTip("창을 화면 오른쪽으로 이동")
        self.pos_right_button.setEnabled(True)
        button_layout.addWidget(self.pos_right_button)
        
        # Resolution presets
        button_layout.addWidget(QLabel("해상도:"))
        
        self.fhd_button = QPushButton("FHD")
        self.fhd_button.setToolTip("1920x1080으로 설정")
        self.fhd_button.setEnabled(True)
        button_layout.addWidget(self.fhd_button)
        
        self.qhd_button = QPushButton("QHD") 
        self.qhd_button.setToolTip("2560x1440으로 설정")
        self.qhd_button.setEnabled(True)
        button_layout.addWidget(self.qhd_button)
        
        self.uhd_button = QPushButton("UHD")
        self.uhd_button.setToolTip("3840x2160으로 설정")
        self.uhd_button.setEnabled(True)
        button_layout.addWidget(self.uhd_button)
        
        self.save_profile_button = QPushButton("선택 항목 프로필에 추가")
        self.save_profile_button.setToolTip("현재 창 설정을 프로필로 저장합니다")
        self.save_profile_button.setEnabled(True)
        button_layout.addWidget(self.save_profile_button)
        
        coords_group_layout.addLayout(button_layout)
        
        # Add coordinate controls group to parent panel
        parent.layout().addWidget(coords_group)
    
    def create_auto_profile_panel(self, parent):
        """Create automatic profile application controls panel - DEPRECATED."""
        # 자동 프로필 패널은 각 프로필별 auto_restore 설정으로 대체되었습니다
        # 이 메소드는 호환성을 위해 유지되지만 더 이상 사용되지 않습니다
        return
        
        # 아래 코드는 주석 처리됨 (더 이상 사용하지 않음)
        """
        auto_apply_group = QGroupBox("자동 프로필 적용")
        # Removed maximum height to allow group to expand
        auto_apply_layout = QVBoxLayout(auto_apply_group)
        
        # Auto-apply master switch
        self.auto_apply_master_checkbox = QCheckBox("자동 프로필 적용 활성화")
        self.auto_apply_master_checkbox.setToolTip("새로운 창이 열릴 때 자동으로 일치하는 프로필을 적용합니다")
        auto_apply_layout.addWidget(self.auto_apply_master_checkbox)
        
        # Settings layout
        settings_layout = QHBoxLayout()
        
        # Monitoring interval
        settings_layout.addWidget(QLabel("감지 간격:"))
        self.monitoring_interval_spinbox = QDoubleSpinBox()
        self.monitoring_interval_spinbox.setMinimum(0.5)
        self.monitoring_interval_spinbox.setMaximum(10.0)
        self.monitoring_interval_spinbox.setValue(1.0)
        self.monitoring_interval_spinbox.setSuffix("초")
        self.monitoring_interval_spinbox.setToolTip("새 창을 확인하는 간격 (초)")
        settings_layout.addWidget(self.monitoring_interval_spinbox)
        
        # Startup delay
        settings_layout.addWidget(QLabel("적용 지연:"))
        self.startup_delay_spinbox = QDoubleSpinBox()
        self.startup_delay_spinbox.setMinimum(0.0)
        self.startup_delay_spinbox.setMaximum(10.0)
        self.startup_delay_spinbox.setValue(2.0)
        self.startup_delay_spinbox.setSuffix("초")
        self.startup_delay_spinbox.setToolTip("창 생성 후 프로필 적용까지 대기 시간")
        settings_layout.addWidget(self.startup_delay_spinbox)
        
        auto_apply_layout.addLayout(settings_layout)
        
        # Status and controls
        status_controls_layout = QHBoxLayout()
        
        # Status display
        self.auto_apply_status_label = QLabel("비활성화됨")
        self.auto_apply_status_label.setStyleSheet("font-weight: bold;")
        status_controls_layout.addWidget(QLabel("상태:"))
        status_controls_layout.addWidget(self.auto_apply_status_label)
        
        
        # Force scan button
        self.force_scan_button = QPushButton("전체 적용")
        self.force_scan_button.setToolTip("모든 열린 창에 대해 일치하는 프로필을 적용합니다")
        self.force_scan_button.setEnabled(True)
        status_controls_layout.addWidget(self.force_scan_button)
        
        auto_apply_layout.addLayout(status_controls_layout)
        
        parent.addWidget(auto_apply_group)
        """
    
    def create_controls_panel(self, parent):
        """Create the controls panel - empty since controls not needed."""
        # Create minimal empty widget to maintain layout structure
        controls_widget = QWidget()
        controls_widget.setMaximumHeight(0)  # Make it invisible
        controls_widget.setMinimumHeight(0)
        
        parent.addWidget(controls_widget)
    
    def create_preset_panel(self, parent):
        """Create the preset controls panel."""
        preset_group = QGroupBox("프리셋 및 검색")
        preset_layout = QVBoxLayout(preset_group)
        
        # Create preset controls widget
        self.preset_controls = PresetControlsWidget()
        preset_layout.addWidget(self.preset_controls)
        
        parent.addWidget(preset_group)
    
    
    def create_coordinate_controls(self, layout):
        """Create coordinate input controls."""
        coord_group = QGroupBox("위치 및 크기")
        coord_group.setMinimumWidth(350)  # 100픽셀 더 넓게
        
        # Use VBox for main layout
        coord_main_layout = QVBoxLayout(coord_group)
        coord_main_layout.setContentsMargins(10, 10, 10, 10)
        coord_main_layout.setSpacing(8)
        
        # Position row with custom styled spinboxes
        position_row = QHBoxLayout()
        position_row.setContentsMargins(0, 0, 0, 0)
        position_row.setSpacing(15)
        
        # X control - with custom prefix using stylesheet
        self.x_spinbox = QSpinBox()
        self.x_spinbox.setRange(-9999, 9999)
        self.x_spinbox.setSuffix(" px")
        self.x_spinbox.setPrefix("X: ")  # Built-in prefix
        self.x_spinbox.setFixedWidth(90)
        self.x_spinbox.setStyleSheet("""
            QSpinBox {
                padding-left: 2px;
                font-size: 11px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 12px;
            }
        """)
        position_row.addWidget(self.x_spinbox)
        
        # Y control - with custom prefix using stylesheet  
        self.y_spinbox = QSpinBox()
        self.y_spinbox.setRange(-9999, 9999)
        self.y_spinbox.setSuffix(" px")
        self.y_spinbox.setPrefix("Y: ")  # Built-in prefix
        self.y_spinbox.setFixedWidth(90)
        self.y_spinbox.setStyleSheet("""
            QSpinBox {
                padding-left: 2px;
                font-size: 11px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 12px;
            }
        """)
        position_row.addWidget(self.y_spinbox)
        
        coord_main_layout.addLayout(position_row)
        
        # Size row
        size_row = QHBoxLayout()
        size_row.setContentsMargins(0, 0, 0, 0)
        size_row.setSpacing(15)
        
        # Width control
        self.width_spinbox = QSpinBox()
        self.width_spinbox.setRange(1, 9999)
        self.width_spinbox.setSuffix(" px")
        self.width_spinbox.setPrefix("폭: ")  # Built-in prefix
        self.width_spinbox.setFixedWidth(100)
        self.width_spinbox.setStyleSheet("""
            QSpinBox {
                padding-left: 2px;
                font-size: 11px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 12px;
            }
        """)
        size_row.addWidget(self.width_spinbox)
        
        # Height control
        self.height_spinbox = QSpinBox()
        self.height_spinbox.setRange(1, 9999)
        self.height_spinbox.setSuffix(" px")
        self.height_spinbox.setPrefix("높이: ")  # Built-in prefix
        self.height_spinbox.setFixedWidth(110)
        self.height_spinbox.setStyleSheet("""
            QSpinBox {
                padding-left: 2px;
                font-size: 11px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 12px;
            }
        """)
        size_row.addWidget(self.height_spinbox)
        
        coord_main_layout.addLayout(size_row)
        
        # Real-time update checkbox
        self.realtime_update_checkbox = QCheckBox("실시간 좌표 추적")
        self.realtime_update_checkbox.setToolTip("선택된 창이 이동할 때 좌표를 실시간으로 업데이트합니다")
        coord_main_layout.addWidget(self.realtime_update_checkbox)
        
        # Profile management section
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("프로필:"))
        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip("저장된 프로필을 선택합니다")
        self.profile_combo.addItem("새 프로필...")
        profile_row.addWidget(self.profile_combo)
        
        # Profile load button
        self.load_profile_button = QPushButton("불러오기")
        self.load_profile_button.setToolTip("선택된 프로필의 설정을 불러옵니다")
        profile_row.addWidget(self.load_profile_button)
        
        coord_main_layout.addLayout(profile_row)
        layout.addWidget(coord_group)
    
    def create_action_buttons(self, layout):
        """Create main action buttons."""
        action_group = QGroupBox("동작")
        action_layout = QVBoxLayout(action_group)
        
        # Primary actions
        primary_layout = QHBoxLayout()
        
        self.apply_button = QPushButton("적용")
        self.apply_button.setToolTip("Apply current position and size to selected window")
        self.apply_button.setStyleSheet("QPushButton { background-color: #3498db; color: white; font-weight: bold; }")
        primary_layout.addWidget(self.apply_button)
        
        self.center_button = QPushButton("가운데 정렬")  
        self.center_button.setToolTip("선택된 창을 화면 가운데에 놓습니다")
        primary_layout.addWidget(self.center_button)
        
        # Resolution presets
        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(QLabel("해상도:"))
        
        self.fhd_button = QPushButton("FHD")
        self.fhd_button.setToolTip("1920x1080으로 설정")
        self.fhd_button.clicked.connect(lambda: self.set_resolution_preset(1920, 1080))
        resolution_layout.addWidget(self.fhd_button)
        
        self.qhd_button = QPushButton("QHD")
        self.qhd_button.setToolTip("2560x1440으로 설정")
        self.qhd_button.clicked.connect(lambda: self.set_resolution_preset(2560, 1440))
        resolution_layout.addWidget(self.qhd_button)
        
        self.uhd_button = QPushButton("UHD")
        self.uhd_button.setToolTip("3840x2160으로 설정")
        self.uhd_button.clicked.connect(lambda: self.set_resolution_preset(3840, 2160))
        resolution_layout.addWidget(self.uhd_button)
        
        primary_layout.addLayout(resolution_layout)
        
        # Position presets
        position_layout = QHBoxLayout()
        position_layout.addWidget(QLabel("위치:"))
        
        self.top_button = QPushButton("위")
        self.top_button.setToolTip("화면 위쪽으로 이동")
        self.top_button.clicked.connect(lambda: self.set_position_preset("top"))
        position_layout.addWidget(self.top_button)
        
        self.bottom_button = QPushButton("아래")
        self.bottom_button.setToolTip("화면 아래쪽으로 이동")
        self.bottom_button.clicked.connect(lambda: self.set_position_preset("bottom"))
        position_layout.addWidget(self.bottom_button)
        
        self.left_button = QPushButton("왼쪽")
        self.left_button.setToolTip("화면 왼쪽으로 이동")
        self.left_button.clicked.connect(lambda: self.set_position_preset("left"))
        position_layout.addWidget(self.left_button)
        
        self.right_button = QPushButton("오른쪽")
        self.right_button.setToolTip("화면 오른쪽으로 이동")
        self.right_button.clicked.connect(lambda: self.set_position_preset("right"))
        position_layout.addWidget(self.right_button)
        
        primary_layout.addLayout(position_layout)
        
        # Initially disable preset buttons (will be enabled when window is selected)
        self.fhd_button.setEnabled(False)
        self.qhd_button.setEnabled(False)
        self.uhd_button.setEnabled(False)
        self.top_button.setEnabled(False)
        self.bottom_button.setEnabled(False)
        self.left_button.setEnabled(False)
        self.right_button.setEnabled(False)
        
        self.get_coords_button = QPushButton("현재 좌표 가져오기")
        self.get_coords_button.setToolTip("선택된 창의 현재 좌표를 위치 및 크기 입력란에 가져옵니다")
        primary_layout.addWidget(self.get_coords_button)
        
        # Profile save/update buttons
        self.save_profile_button = QPushButton("프로필 저장")
        self.save_profile_button.setToolTip("현재 설정을 프로필로 저장합니다")
        self.save_profile_button.setStyleSheet("QPushButton { background-color: #27ae60; color: white; font-weight: bold; }")
        primary_layout.addWidget(self.save_profile_button)
        
        self.update_profile_button = QPushButton("프로필 업데이트")
        self.update_profile_button.setToolTip("선택된 프로필을 현재 설정으로 업데이트합니다")
        self.update_profile_button.setStyleSheet("QPushButton { background-color: #f39c12; color: white; font-weight: bold; }")
        self.update_profile_button.setEnabled(False)  # Initially disabled
        primary_layout.addWidget(self.update_profile_button)
        
        action_layout.addLayout(primary_layout)
        
        # Secondary actions
        secondary_layout = QHBoxLayout()
        
        self.minimize_button = QPushButton("최소화")
        secondary_layout.addWidget(self.minimize_button)
        
        self.maximize_button = QPushButton("최대화")
        secondary_layout.addWidget(self.maximize_button)
        
        self.restore_button = QPushButton("복원")
        secondary_layout.addWidget(self.restore_button)
        
        action_layout.addLayout(secondary_layout)
        
        layout.addWidget(action_group)
    
    def create_quick_actions(self, layout):
        """Create quick action buttons."""
        quick_group = QGroupBox("빠른 동작")
        quick_layout = QGridLayout(quick_group)
        
        # Snap buttons
        self.snap_left_button = QPushButton("◀ 왼쪽")
        self.snap_left_button.setToolTip("Snap to left half of screen")
        quick_layout.addWidget(self.snap_left_button, 0, 0)
        
        self.snap_right_button = QPushButton("오른쪽 ▶")
        self.snap_right_button.setToolTip("Snap to right half of screen")
        quick_layout.addWidget(self.snap_right_button, 0, 1)
        
        self.snap_top_button = QPushButton("▲ 위쪽")
        self.snap_top_button.setToolTip("Snap to top half of screen")
        quick_layout.addWidget(self.snap_top_button, 1, 0)
        
        self.snap_bottom_button = QPushButton("아래쪽 ▼")
        self.snap_bottom_button.setToolTip("Snap to bottom half of screen")
        quick_layout.addWidget(self.snap_bottom_button, 1, 1)
        
        # Common sizes
        size_layout = QHBoxLayout()
        
        self.size_1024_button = QPushButton("1024×768")
        self.size_1024_button.setToolTip("Resize to 1024×768")
        size_layout.addWidget(self.size_1024_button)
        
        self.size_1280_button = QPushButton("1280×720")
        self.size_1280_button.setToolTip("Resize to 1280×720")
        size_layout.addWidget(self.size_1280_button)
        
        quick_layout.addLayout(size_layout, 2, 0, 1, 2)
        
        layout.addWidget(quick_group)
    
    def setup_menu_bar(self):
        """Setup the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('파일')
        
        refresh_action = QAction('창 목록 새로고침', self)
        refresh_action.setShortcut('F5')
        refresh_action.setToolTip('활성창 목록을 새로고침합니다')
        refresh_action.triggered.connect(self.refresh_window_list)
        file_menu.addAction(refresh_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('종료', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setToolTip('프로그램을 종료합니다')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Tools menu (제거된 기능들 접근용)
        tools_menu = menubar.addMenu('도구')
        
        search_action = QAction('검색 및 필터', self)
        search_action.setShortcut('Ctrl+F')
        search_action.setToolTip('창 검색 및 필터 도구를 엽니다')
        search_action.triggered.connect(self.show_search_dialog)
        tools_menu.addAction(search_action)
        
        coords_action = QAction('좌표 조정', self)
        coords_action.setShortcut('Ctrl+M')
        coords_action.setToolTip('창 크기 및 위치 조정 도구를 엽니다')
        coords_action.triggered.connect(self.show_coords_dialog)
        tools_menu.addAction(coords_action)
        
        auto_apply_action = QAction('자동 적용 설정', self)
        auto_apply_action.setShortcut('Ctrl+A')
        auto_apply_action.setToolTip('자동 프로필 적용 설정을 엽니다')
        auto_apply_action.triggered.connect(self.show_auto_apply_dialog)
        tools_menu.addAction(auto_apply_action)
        
        tools_menu.addSeparator()
        
        debug_action = QAction('디버그 창 열기', self)
        debug_action.setShortcut('Ctrl+D')
        debug_action.setToolTip('실시간 디버그 메시지 출력 창을 엽니다')
        debug_action.triggered.connect(self.show_debug_window)
        tools_menu.addAction(debug_action)
        
        # Profile menu (메인 GUI와 일치하도록 개편)
        profile_menu = menubar.addMenu('프로필')
        
        # 선택 항목 프로필에 추가
        add_to_profile_action = QAction('선택 항목 프로필에 추가', self)
        add_to_profile_action.setShortcut('Ctrl+S')
        add_to_profile_action.setToolTip('선택된 창을 새 프로필로 저장합니다')
        add_to_profile_action.triggered.connect(self.add_selected_to_profile)
        profile_menu.addAction(add_to_profile_action)
        
        # 프로필 편집
        edit_profile_action = QAction('프로필 편집', self)
        edit_profile_action.setShortcut('Ctrl+E')
        edit_profile_action.setToolTip('선택된 프로필을 편집합니다')
        edit_profile_action.triggered.connect(self.edit_selected_profile)
        profile_menu.addAction(edit_profile_action)
        
        # 프로필 삭제
        delete_profile_action = QAction('프로필 삭제', self)
        delete_profile_action.setShortcut('Delete')
        delete_profile_action.setToolTip('선택된 프로필을 삭제합니다')
        delete_profile_action.triggered.connect(self.delete_selected_profile)
        profile_menu.addAction(delete_profile_action)
        
        profile_menu.addSeparator()
        
        # 프로필 적용
        apply_profile_action = QAction('프로필 적용', self)
        apply_profile_action.setShortcut('Ctrl+A')
        apply_profile_action.setToolTip('선택된 프로필을 일치하는 창에 적용합니다')
        apply_profile_action.triggered.connect(self.apply_selected_profile)
        profile_menu.addAction(apply_profile_action)
        
        # 전체 적용
        apply_all_action = QAction('전체 적용', self)
        apply_all_action.setToolTip('모든 프로필을 일치하는 창에 적용합니다')
        apply_all_action.triggered.connect(self.auto_apply_profiles)
        profile_menu.addAction(apply_all_action)
        
        # View menu
        view_menu = menubar.addMenu('보기')
        
        self.safe_mode_action = QAction('안전 모드', self)
        self.safe_mode_action.setCheckable(True)
        self.safe_mode_action.setToolTip('안전 모드를 활성화합니다 (읽기 전용)')
        self.safe_mode_action.triggered.connect(self.toggle_safe_mode)
        view_menu.addAction(self.safe_mode_action)
        
        # Theme menu
        theme_menu = menubar.addMenu('테마')
        
        light_theme_action = QAction('밝은 테마', self)
        light_theme_action.setToolTip('밝은 테마로 변경합니다')
        light_theme_action.triggered.connect(lambda: self.theme_manager.set_theme(ThemeType.LIGHT, "Light"))
        theme_menu.addAction(light_theme_action)
        
        dark_theme_action = QAction('어두운 테마', self)
        dark_theme_action.setToolTip('어두운 테마로 변경합니다')
        dark_theme_action.triggered.connect(lambda: self.theme_manager.set_theme(ThemeType.DARK, "Dark"))
        theme_menu.addAction(dark_theme_action)
        
        high_contrast_action = QAction('고대비 테마', self)
        high_contrast_action.setToolTip('고대비 테마로 변경합니다')
        high_contrast_action.triggered.connect(lambda: self.theme_manager.set_theme(ThemeType.CUSTOM, "High Contrast"))
        theme_menu.addAction(high_contrast_action)
        
        theme_menu.addSeparator()
        
        system_theme_action = QAction('시스템 테마 따르기', self)
        system_theme_action.setCheckable(True)
        system_theme_action.setChecked(self.theme_manager.follow_system)
        system_theme_action.setToolTip('운영체제의 테마 설정을 따릅니다')
        system_theme_action.triggered.connect(lambda checked: self.theme_manager.set_follow_system(checked))
        theme_menu.addAction(system_theme_action)
        
        # Help menu
        help_menu = menubar.addMenu('도움말')
        
        about_action = QAction('정보', self)
        about_action.setToolTip('프로그램 정보를 표시합니다')
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_status_bar(self):
        """Setup the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Status message
        self.status_label = QLabel("준비")
        self.status_bar.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Privilege status
        self.privilege_label = QLabel()
        self.update_privilege_status()
        self.status_bar.addPermanentWidget(self.privilege_label)
        
        # Connection status
        self.connection_label = QLabel("시스템: 연결됨")
        self.connection_label.setStyleSheet("color: green;")
        self.status_bar.addPermanentWidget(self.connection_label)

        self.quit_application_button = QPushButton("프로그램 종료")
        self.quit_application_button.setToolTip("WindowResizer를 완전히 종료합니다")
        self.quit_application_button.clicked.connect(self.quit_application)
        self.status_bar.addPermanentWidget(self.quit_application_button)
    
    def update_privilege_status(self):
        """Update privilege status indicator."""
        try:
            import ctypes
            import os
            
            # Check if running as administrator
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            
            if is_admin:
                self.privilege_label.setText("권한: 관리자")
                self.privilege_label.setStyleSheet("color: green; font-weight: bold;")
                self.privilege_label.setToolTip("관리자 권한으로 실행 중입니다. 모든 창을 제어할 수 있습니다.")
            else:
                self.privilege_label.setText("권한: 일반사용자")
                self.privilege_label.setStyleSheet("color: orange; font-weight: bold;")
                self.privilege_label.setToolTip("일반 사용자 권한으로 실행 중입니다. 일부 시스템 창은 제어하지 못할 수 있습니다.\n관리자 권한이 필요한 경우 start_windowresizer_admin.bat을 사용하세요.")
                
        except Exception as e:
            self.privilege_label.setText("권한: 알 수 없음")
            self.privilege_label.setStyleSheet("color: gray;")
            logger.debug(f"Failed to check privilege status: {e}")
    
    def setup_timers(self):
        """Setup timers for automatic updates."""
        # Auto-refresh timer
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.auto_refresh_windows)
        self.auto_refresh_timer.setInterval(5000)  # 5초로 변경
        
        # Real-time coordinate update timer
        self.coordinate_timer = QTimer()
        self.coordinate_timer.timeout.connect(self.update_current_window_coordinates)
        self.coordinate_timer.setInterval(500)  # 0.5 seconds
    
    def setup_connections(self):
        """Setup signal connections."""
        try:
            # Window list (QTableWidget)
            self.window_list_widget.itemSelectionChanged.connect(self.on_window_selected)
            
            # Core control buttons (safe connection with hasattr and try-except)
            if hasattr(self, 'refresh_button'):
                try:
                    self.refresh_button.clicked.connect(self.refresh_window_list)
                except RuntimeError:
                    pass  # Button was deleted
            if hasattr(self, 'apply_button'):
                try:
                    self.apply_button.clicked.connect(self.apply_coordinates)
                except RuntimeError:
                    pass  # Button was deleted
            if hasattr(self, 'center_button'):
                try:
                    self.center_button.clicked.connect(self.center_window)
                except RuntimeError:
                    pass  # Button was deleted
                    
            # Connect preset buttons
            if hasattr(self, 'fhd_button'):
                try:
                    self.fhd_button.clicked.connect(lambda: self.apply_resolution_preset(1920, 1080))
                except RuntimeError:
                    pass
            if hasattr(self, 'qhd_button'):
                try:
                    self.qhd_button.clicked.connect(lambda: self.apply_resolution_preset(2560, 1440))
                except RuntimeError:
                    pass
            if hasattr(self, 'uhd_button'):
                try:
                    self.uhd_button.clicked.connect(lambda: self.apply_resolution_preset(3840, 2160))
                except RuntimeError:
                    pass
            if hasattr(self, 'pos_up_button'):
                try:
                    self.pos_up_button.clicked.connect(lambda: self.apply_position_preset("up"))
                except RuntimeError:
                    pass
            if hasattr(self, 'pos_down_button'):
                try:
                    self.pos_down_button.clicked.connect(lambda: self.apply_position_preset("down"))
                except RuntimeError:
                    pass
            if hasattr(self, 'pos_left_button'):
                try:
                    self.pos_left_button.clicked.connect(lambda: self.apply_position_preset("left"))
                except RuntimeError:
                    pass
            if hasattr(self, 'pos_right_button'):
                try:
                    self.pos_right_button.clicked.connect(lambda: self.apply_position_preset("right"))
                except RuntimeError:
                    pass
            if hasattr(self, 'get_coords_button'):
                try:
                    self.get_coords_button.clicked.connect(self.get_current_coordinates)
                except RuntimeError:
                    pass  # Button was deleted
            if hasattr(self, 'save_profile_button'):
                try:
                    self.save_profile_button.clicked.connect(self.save_current_as_profile)
                except RuntimeError:
                    pass  # Button was deleted
            if hasattr(self, 'load_profile_button'):
                try:
                    self.load_profile_button.clicked.connect(self.load_selected_profile)
                except RuntimeError:
                    pass  # Button was deleted
        
            # Auto-apply system connections (safe connection)
            if hasattr(self, 'auto_apply_master_checkbox'):
                try:
                    self.auto_apply_master_checkbox.toggled.connect(self.toggle_auto_apply)
                except RuntimeError:
                    pass  # Widget was deleted
            if hasattr(self, 'monitoring_interval_spinbox'):
                try:
                    self.monitoring_interval_spinbox.valueChanged.connect(self.update_monitoring_config)
                except RuntimeError:
                    pass  # Widget was deleted
            if hasattr(self, 'startup_delay_spinbox'):
                try:
                    self.startup_delay_spinbox.valueChanged.connect(self.update_monitoring_config)
                except RuntimeError:
                    pass  # Widget was deleted
            if hasattr(self, 'force_scan_button'):
                try:
                    self.force_scan_button.clicked.connect(self.force_scan_windows)
                except RuntimeError:
                    pass  # Widget was deleted
            if hasattr(self, 'update_profile_button'):
                try:
                    self.update_profile_button.clicked.connect(self.update_selected_profile)
                except RuntimeError:
                    pass  # Widget was deleted
        
            # Profile management buttons (safe connection)
            if hasattr(self, 'edit_profile_button'):
                try:
                    self.edit_profile_button.clicked.connect(self.edit_selected_profile)
                except RuntimeError:
                    pass  # Widget was deleted
            if hasattr(self, 'delete_profile_button'):
                try:
                    self.delete_profile_button.clicked.connect(self.delete_selected_profile)
                except RuntimeError:
                    pass  # Widget was deleted
            if hasattr(self, 'apply_profile_button'):
                try:
                    self.apply_profile_button.clicked.connect(self.apply_selected_profile)
                except RuntimeError:
                    pass  # Widget was deleted
            if hasattr(self, 'apply_all_profiles_button'):
                try:
                    self.apply_all_profiles_button.clicked.connect(self.auto_apply_profiles)
                except RuntimeError:
                    pass  # Widget was deleted
            
            # Search connections
            if hasattr(self, 'search_button'):
                try:
                    self.search_button.clicked.connect(self.perform_search)
                except RuntimeError:
                    pass  # Widget was deleted
            
            # Theme toggle connection
            if hasattr(self, 'theme_toggle_button'):
                try:
                    self.theme_toggle_button.clicked.connect(self.toggle_theme)
                except RuntimeError:
                    pass  # Widget was deleted
            
            # Profile table selection
            if hasattr(self, 'profile_table_widget'):
                try:
                    self.profile_table_widget.itemSelectionChanged.connect(self.on_profile_selected)
                except RuntimeError:
                    pass  # Widget was deleted
        
        except Exception as e:
            logger.error(f"Error setting up connections: {e}")
        # self.maximize_button.clicked.connect(self.maximize_window)
        # self.restore_button.clicked.connect(self.restore_window)
        
        # Snap buttons (temporarily commented out)
        # self.snap_left_button.clicked.connect(lambda: self.snap_window('left'))
        # self.snap_right_button.clicked.connect(lambda: self.snap_window('right'))
        # self.snap_top_button.clicked.connect(lambda: self.snap_window('top'))
        # self.snap_bottom_button.clicked.connect(lambda: self.snap_window('bottom'))
        
        # Size buttons (temporarily commented out)
        # self.size_1024_button.clicked.connect(lambda: self.resize_window_to(1024, 768))
        # self.size_1280_button.clicked.connect(lambda: self.resize_window_to(1280, 720))
        
        # Auto-refresh checkbox
        if hasattr(self, 'auto_refresh_checkbox'):
            self.auto_refresh_checkbox.toggled.connect(self.toggle_auto_refresh)
        
        # Real-time coordinates checkbox
        if hasattr(self, 'realtime_update_checkbox'):
            self.realtime_update_checkbox.toggled.connect(self.toggle_realtime_coordinates)
        
        # Profile selection
        if hasattr(self, 'profile_combo'):
            self.profile_combo.currentTextChanged.connect(self.on_profile_selection_changed)
        
        # Search input and buttons (temporarily disabled)
        # self.search_input.textChanged.connect(self.filter_windows)
        # if hasattr(self, 'search_button'):
        #     self.search_button.clicked.connect(self.filter_windows)
        # if hasattr(self, 'add_to_profile_button'):
        #     self.add_to_profile_button.clicked.connect(self.add_selected_window_to_profile)
        # 
        # # Filter combo
        # self.filter_combo.currentTextChanged.connect(self.filter_windows)
        
        # Preset controls connections
        if self.preset_controls:
            self.preset_controls.preset_applied.connect(self.on_preset_applied)
            self.preset_controls.window_selected.connect(self.on_preset_window_selected)
        
        # Theme manager connections
        if self.theme_manager:
            self.theme_manager.theme_changed.connect(self.on_theme_changed)
        
        # Start auto-refresh if enabled
        if hasattr(self, 'auto_refresh_checkbox') and self.auto_refresh_checkbox.isChecked():
            self.auto_refresh_timer.start()
    
    def setup_window_constraints(self):
        """Fit the initial main window within the primary screen work area."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return

        available_geometry = screen.availableGeometry()
        min_width, min_height, max_width, max_height, default_width, default_height = (
            self.calculate_window_size_constraints(available_geometry)
        )
        self.setMinimumSize(min_width, min_height)
        self.setMaximumSize(max_width, max_height)
        self.resize(default_width, default_height)

        self.center_on_screen(available_geometry)

    @staticmethod
    def calculate_window_size_constraints(available_geometry: QRect):
        """Return screen-safe minimum, maximum, and initial window dimensions."""
        min_width = min(900, available_geometry.width())
        min_height = min(720, available_geometry.height())
        max_width = max(min_width, min(1600, available_geometry.width()))
        max_height = max(min_height, min(1000, available_geometry.height()))
        default_width = min(max_width, max(min_width, 1150))
        default_height = min(max_height, max(min_height, 800))
        return min_width, min_height, max_width, max_height, default_width, default_height
    
    def center_on_screen(self, available_geometry: Optional[QRect] = None):
        """Center the window on the screen."""
        try:
            if available_geometry is None:
                screen = QApplication.primaryScreen()
                if screen is None:
                    return
                available_geometry = screen.availableGeometry()

            x = available_geometry.x() + max(0, (available_geometry.width() - self.width()) // 2)
            y = available_geometry.y() + max(0, (available_geometry.height() - self.height()) // 2)
            self.move(x, y)
        except Exception as e:
            logger.debug(f"Could not center window: {e}")

    @staticmethod
    def calculate_position_in_work_area(position: str, width: int, height: int,
                                        work_area, margin: int = 0):
        """Calculate an edge preset in one Win32 monitor work area."""
        left, top, right, bottom = work_area
        available_width = right - left
        available_height = bottom - top
        horizontal_margin = min(margin, max(0, available_width // 2))
        vertical_margin = min(margin, max(0, available_height // 2))

        if position in ("top", "up"):
            x = left + (available_width - width) // 2
            y = top + vertical_margin
        elif position in ("bottom", "down"):
            x = left + (available_width - width) // 2
            y = bottom - height - vertical_margin
        elif position == "left":
            x = left + horizontal_margin
            y = top + (available_height - height) // 2
        elif position == "right":
            x = right - width - horizontal_margin
            y = top + (available_height - height) // 2
        else:
            raise ValueError(f"Unsupported position preset: {position}")

        max_x = max(left, right - width)
        max_y = max(top, bottom - height)
        return max(left, min(x, max_x)), max(top, min(y, max_y))

    @staticmethod
    def get_work_area_for_window(hwnd: int):
        """Return the target window monitor work area in Win32 native coordinates."""
        import win32api
        import win32con

        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        return win32api.GetMonitorInfo(monitor)["Work"]

    def apply_styling(self):
        """Apply theme-based styling to the GUI."""
        self.apply_theme_styling()
    
    def apply_theme_styling(self):
        """Apply theme-based styling to all UI elements."""
        try:
            current_theme = self.theme_manager.current_theme
            
            # Convert to string if it's an enum
            if hasattr(current_theme, 'value'):
                theme_str = current_theme.value
            else:
                theme_str = str(current_theme).lower()
            
            logger.info(f"Applying theme styling for: {theme_str}")

            if self.theme_manager.current_scheme:
                bg = self.theme_manager.get_color_string(ThemeElement.BACKGROUND)
                fg = self.theme_manager.get_color_string(ThemeElement.FOREGROUND)
                button = self.theme_manager.get_color_string(ThemeElement.BUTTON)
                button_hover = self.theme_manager.get_color_string(ThemeElement.BUTTON_HOVER)
                button_pressed = self.theme_manager.get_color_string(ThemeElement.BUTTON_PRESSED)
                text = self.theme_manager.get_color_string(ThemeElement.TEXT)
                accent = self.theme_manager.get_color_string(ThemeElement.ACCENT)
                border = self.theme_manager.get_color_string(ThemeElement.BORDER)
                disabled = self.theme_manager.get_color_string(ThemeElement.DISABLED)

                self.setStyleSheet(f"""
                    QMainWindow {{ background-color: {bg}; color: {text}; }}
                    QWidget {{ color: {text}; }}
                    QGroupBox {{
                        background-color: {fg}; border: 1px solid {border}; border-radius: 5px;
                        margin-top: 10px; padding-top: 5px; font-weight: bold;
                    }}
                    QGroupBox::title {{
                        subcontrol-origin: margin; left: 10px; padding: 0 5px; color: {text};
                    }}
                    QLabel {{ color: {text}; background-color: transparent; }}
                    QPushButton {{
                        background-color: {button}; color: {text}; border: 1px solid {border};
                        border-radius: 3px; padding: 5px 10px; font-weight: bold;
                    }}
                    QPushButton:hover {{ background-color: {button_hover}; }}
                    QPushButton:pressed {{ background-color: {button_pressed}; }}
                    QPushButton:disabled {{ background-color: {button_pressed}; color: {disabled}; }}
                    QLineEdit, QSpinBox, QComboBox, QTextEdit {{
                        background-color: {fg}; color: {text}; border: 1px solid {border};
                        border-radius: 3px; padding: 3px;
                    }}
                    QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
                        border: 2px solid {accent};
                    }}
                    QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {{
                        background-color: {button}; border: none;
                    }}
                    QComboBox::down-arrow {{
                        image: none; border-left: 5px solid transparent;
                        border-right: 5px solid transparent; border-top: 5px solid {text};
                    }}
                    QComboBox QAbstractItemView {{
                        background-color: {fg}; color: {text}; border: 1px solid {border};
                        selection-background-color: {accent}; selection-color: {bg};
                    }}
                    QCheckBox, QRadioButton {{ color: {text}; }}
                    QCheckBox::indicator, QRadioButton::indicator {{
                        background-color: {fg}; border: 1px solid {border};
                    }}
                    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
                        background-color: {accent};
                    }}
                    QListWidget, QTableWidget {{
                        background-color: {fg}; color: {text}; border: 1px solid {border};
                    }}
                    QTableWidget::item {{ background-color: {fg}; color: {text}; }}
                    QTableWidget::item:alternate {{ background-color: {button}; color: {text}; }}
                    QListWidget::item:selected, QTableWidget::item:selected {{
                        background-color: {accent}; color: {bg};
                    }}
                    QHeaderView::section {{
                        background-color: {button}; color: {text}; border: 1px solid {border}; padding: 4px;
                    }}
                    QProgressBar {{
                        background-color: {fg}; color: {text}; border: 1px solid {border}; text-align: center;
                    }}
                    QProgressBar::chunk {{ background-color: {accent}; }}
                    QStatusBar {{ background-color: {fg}; color: {text}; border-top: 1px solid {border}; }}
                    QMenuBar, QMenu {{ background-color: {fg}; color: {text}; border: 1px solid {border}; }}
                    QMenuBar::item:selected, QMenu::item:selected {{ background-color: {accent}; color: {bg}; }}
                """)
                return
            
            if theme_str == "dark":
                # Dark theme styles
                self.setStyleSheet("""
                    QMainWindow {
                        background-color: #2b2b2b;
                        color: #ffffff;
                    }
                    QGroupBox {
                        background-color: #3c3c3c;
                        color: #ffffff;
                        border: 2px solid #555555;
                        border-radius: 5px;
                        margin-top: 10px;
                        padding-top: 10px;
                        font-weight: bold;
                    }
                    QGroupBox::title {
                        color: #ffffff;
                        subcontrol-origin: margin;
                        left: 10px;
                        padding: 0 5px 0 5px;
                    }
                    QLabel {
                        color: #ffffff;
                        background-color: transparent;
                    }
                    QPushButton {
                        background-color: #4a4a4a;
                        color: #ffffff;
                        border: 1px solid #666666;
                        border-radius: 3px;
                        padding: 5px 10px;
                        min-height: 20px;
                    }
                    QPushButton:hover {
                        background-color: #5a5a5a;
                        border: 1px solid #777777;
                    }
                    QPushButton:pressed {
                        background-color: #3a3a3a;
                    }
                    QPushButton:disabled {
                        background-color: #333333;
                        color: #666666;
                        border-color: #444444;
                    }
                    QLineEdit, QSpinBox {
                        background-color: #404040;
                        color: #ffffff;
                        border: 1px solid #666666;
                        border-radius: 3px;
                        padding: 5px;
                    }
                    QSpinBox::up-button, QSpinBox::down-button {
                        background-color: #4a4a4a;
                        color: #ffffff;
                        border: 1px solid #666666;
                    }
                    QComboBox {
                        background-color: #404040;
                        color: #ffffff;
                        border: 1px solid #666666;
                        border-radius: 3px;
                        padding: 5px;
                    }
                    QComboBox::drop-down {
                        border: none;
                        background-color: #4a4a4a;
                    }
                    QComboBox::down-arrow {
                        image: none;
                        border-left: 5px solid transparent;
                        border-right: 5px solid transparent;
                        border-top: 5px solid #ffffff;
                    }
                    QComboBox QAbstractItemView {
                        background-color: #404040;
                        color: #ffffff;
                        border: 1px solid #666666;
                        selection-background-color: #4a90e2;
                    }
                    QCheckBox {
                        color: #ffffff;
                        spacing: 5px;
                    }
                    QCheckBox::indicator {
                        width: 13px;
                        height: 13px;
                        background-color: #404040;
                        border: 1px solid #666666;
                        border-radius: 2px;
                    }
                    QCheckBox::indicator:checked {
                        background-color: #4a90e2;
                        border: 1px solid #4a90e2;
                    }
                    QTableWidget {
                        background-color: #3c3c3c;
                        color: #ffffff;
                        gridline-color: #555555;
                        selection-background-color: #4a90e2;
                        alternate-background-color: #404040;
                        border: 1px solid #555555;
                        border-radius: 3px;
                    }
                    QTableWidget::item {
                        color: #ffffff;
                        background-color: transparent;
                        border: none;
                        padding: 3px;
                    }
                    QTableWidget::item:selected {
                        background-color: #4a90e2;
                        color: #ffffff;
                    }
                    QTableWidget QHeaderView::section {
                        background-color: #4a4a4a;
                        color: #ffffff;
                        border: 1px solid #666666;
                        padding: 5px;
                    }
                    QProgressBar {
                        background-color: #404040;
                        color: #ffffff;
                        border: 1px solid #666666;
                        border-radius: 3px;
                        text-align: center;
                    }
                    QProgressBar::chunk {
                        background-color: #4a90e2;
                    }
                    QStatusBar {
                        background-color: #2b2b2b;
                        color: #ffffff;
                    }
                    QMenuBar {
                        background-color: #3c3c3c;
                        color: #ffffff;
                        border-bottom: 1px solid #555555;
                    }
                    QMenuBar::item {
                        background-color: transparent;
                        color: #ffffff;
                        padding: 5px 10px;
                    }
                    QMenuBar::item:selected {
                        background-color: #4a90e2;
                    }
                    QMenu {
                        background-color: #3c3c3c;
                        color: #ffffff;
                        border: 1px solid #555555;
                    }
                    QMenu::item {
                        padding: 5px 15px;
                        background-color: transparent;
                    }
                    QMenu::item:selected {
                        background-color: #4a90e2;
                    }
                """)
            else:
                # Light theme styles
                self.setStyleSheet("""
                    QMainWindow {
                        background-color: #f8f9fa;
                        color: #000000;
                    }
                    QGroupBox {
                        background-color: #ffffff;
                        color: #000000;
                        border: 2px solid #dee2e6;
                        border-radius: 5px;
                        margin-top: 10px;
                        padding-top: 10px;
                        font-weight: bold;
                    }
                    QGroupBox::title {
                        color: #495057;
                        subcontrol-origin: margin;
                        left: 10px;
                        padding: 0 5px 0 5px;
                    }
                    QLabel {
                        color: #000000;
                        background-color: transparent;
                    }
                    QPushButton {
                        background-color: #e9ecef;
                        color: #000000;
                        border: 1px solid #ced4da;
                        border-radius: 3px;
                        padding: 5px 10px;
                        min-height: 20px;
                    }
                    QPushButton:hover {
                        background-color: #dee2e6;
                        border-color: #adb5bd;
                    }
                    QPushButton:pressed {
                        background-color: #ced4da;
                    }
                    QPushButton:disabled {
                        background-color: #f8f9fa;
                        color: #6c757d;
                        border-color: #dee2e6;
                    }
                    QLineEdit, QSpinBox {
                        background-color: #ffffff;
                        color: #000000;
                        border: 1px solid #ced4da;
                        border-radius: 3px;
                        padding: 5px;
                    }
                    QSpinBox::up-button, QSpinBox::down-button {
                        background-color: #e9ecef;
                        color: #000000;
                        border: 1px solid #ced4da;
                    }
                    QComboBox {
                        background-color: #ffffff;
                        color: #000000;
                        border: 1px solid #ced4da;
                        border-radius: 3px;
                        padding: 5px;
                    }
                    QComboBox::drop-down {
                        border: none;
                        background-color: #e9ecef;
                    }
                    QComboBox::down-arrow {
                        image: none;
                        border-left: 5px solid transparent;
                        border-right: 5px solid transparent;
                        border-top: 5px solid #000000;
                    }
                    QComboBox QAbstractItemView {
                        background-color: #ffffff;
                        color: #000000;
                        border: 1px solid #ced4da;
                        selection-background-color: #007bff;
                        selection-color: #ffffff;
                    }
                    QCheckBox {
                        color: #000000;
                        spacing: 5px;
                    }
                    QCheckBox::indicator {
                        width: 13px;
                        height: 13px;
                        background-color: #ffffff;
                        border: 1px solid #ced4da;
                        border-radius: 2px;
                    }
                    QCheckBox::indicator:checked {
                        background-color: #007bff;
                        border: 1px solid #007bff;
                    }
                    QTableWidget {
                        background-color: #ffffff;
                        color: #000000;
                        gridline-color: #dee2e6;
                        selection-background-color: #007bff;
                        alternate-background-color: #f8f9fa;
                        border: 1px solid #dee2e6;
                        border-radius: 3px;
                    }
                    QTableWidget::item {
                        color: #000000;
                        background-color: transparent;
                        border: none;
                        padding: 3px;
                    }
                    QTableWidget::item:selected {
                        background-color: #007bff;
                        color: #ffffff;
                    }
                    QTableWidget QHeaderView::section {
                        background-color: #e9ecef;
                        color: #495057;
                        border: 1px solid #ced4da;
                        padding: 5px;
                    }
                    QProgressBar {
                        background-color: #ffffff;
                        color: #000000;
                        border: 1px solid #ced4da;
                        border-radius: 3px;
                        text-align: center;
                    }
                    QProgressBar::chunk {
                        background-color: #007bff;
                    }
                    QStatusBar {
                        background-color: #f8f9fa;
                        color: #000000;
                    }
                    QMenuBar {
                        background-color: #ffffff;
                        color: #000000;
                        border-bottom: 1px solid #dee2e6;
                    }
                    QMenuBar::item {
                        background-color: transparent;
                        color: #000000;
                        padding: 5px 10px;
                    }
                    QMenuBar::item:selected {
                        background-color: #007bff;
                        color: #ffffff;
                    }
                    QMenu {
                        background-color: #ffffff;
                        color: #000000;
                        border: 1px solid #dee2e6;
                    }
                    QMenu::item {
                        padding: 5px 15px;
                        background-color: transparent;
                    }
                    QMenu::item:selected {
                        background-color: #007bff;
                        color: #ffffff;
                    }
                """)
                
        except Exception as e:
            logger.error(f"Error applying theme styling: {e}")
    
    def refresh_window_list(self, on_complete=None):
        """Refresh the window list and optionally continue with the fresh results."""
        self.status_label.setText("창 목록을 새로고침 중...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        # Start background thread for window enumeration
        if self.update_thread and self.update_thread.isRunning():
            self.update_thread.quit()
            self.update_thread.wait()
        
        self.update_thread = WindowUpdateThread()
        self.update_thread.on_complete = on_complete
        self.update_thread.windows_updated.connect(self.on_windows_updated)
        self.update_thread.error_occurred.connect(self.on_update_error)
        self.update_thread.start()
    
    def on_windows_updated(self, windows: List[WindowInfo]):
        """Handle window list update."""
        update_thread = self.sender()
        on_complete = getattr(update_thread, "on_complete", None)
        if update_thread is not None:
            update_thread.on_complete = None

        # Store current selection if any
        current_hwnd = self.current_window.hwnd if self.current_window else None
        
        self.window_list = windows
        self.cached_windows = windows  # Cache windows for selection resolution
        self.update_window_list_display()
        
        # Try to restore selection if it still exists
        if current_hwnd:
            self.restore_window_selection(current_hwnd)
        
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"창 {len(windows)}개를 찾았습니다")
        
        logger.info(f"Window list updated: {len(windows)} windows")

        if on_complete:
            on_complete(windows)
    
    def on_update_error(self, error_message: str):
        """Handle window update error."""
        update_thread = self.sender()
        if update_thread is not None:
            update_thread.on_complete = None

        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Error: {error_message}")
        
        QMessageBox.warning(self, "Window Update Error", 
                          f"Failed to update window list:\n{error_message}")
        
        logger.error(f"Window update error: {error_message}")
    
    def update_window_list_display(self):
        """Update the window list display with current windows (QTableWidget)."""
        # Temporarily disable sorting to prevent issues during updates
        self.window_list_widget.setSortingEnabled(False)
        
        # Clear existing rows
        self.window_list_widget.setRowCount(0)
        
        # Apply filters
        filtered_windows = self.apply_window_filters()
        
        # Set row count
        self.window_list_widget.setRowCount(len(filtered_windows))
        
        for row, window in enumerate(filtered_windows):
            # Create state indicators
            state_indicators = []
            if window.is_minimized:
                state_indicators.append("MIN")
            if window.is_maximized:
                state_indicators.append("MAX")
            if not window.is_visible:
                state_indicators.append("HIDDEN")
            
            state_text = f" [{', '.join(state_indicators)}]" if state_indicators else ""
            
            # Column 0: Window Title with state
            title_item = QTableWidgetItem(f"{window.title}{state_text}")
            title_item.setData(Qt.UserRole, window)  # Store window info in first column
            
            # Column 1: PID - Get from window directly
            pid_text = "Unknown"
            if hasattr(window, 'pid') and window.pid > 0:
                pid_text = str(window.pid)
            pid_item = QTableWidgetItem(pid_text)
            if pid_text != "Unknown":
                pid_item.setData(Qt.UserRole + 1, int(pid_text))  # For numeric sorting
            
            # Column 2: Process Name
            process_item = QTableWidgetItem(window.process_name)
            
            # Column 3-6: Coordinates (X, Y, Width, Height)
            x_item = QTableWidgetItem(str(window.rect.left))
            y_item = QTableWidgetItem(str(window.rect.top))
            width_item = QTableWidgetItem(str(window.rect.width))
            height_item = QTableWidgetItem(str(window.rect.height))
            
            # Set numeric data for proper sorting
            x_item.setData(Qt.UserRole + 1, window.rect.left)
            y_item.setData(Qt.UserRole + 1, window.rect.top) 
            width_item.setData(Qt.UserRole + 1, window.rect.width)
            height_item.setData(Qt.UserRole + 1, window.rect.height)
            
            # Set item colors based on state
            color = None
            if window.is_minimized:
                color = QColor("#6c757d")  # Gray for minimized
            elif not window.is_visible:
                color = QColor("#dc3545")  # Red for hidden
            
            items = [title_item, pid_item, process_item, x_item, y_item, width_item, height_item]
            
            if color:
                for item in items:
                    item.setForeground(color)
            
            # Add items to table
            self.window_list_widget.setItem(row, 0, title_item)
            self.window_list_widget.setItem(row, 1, pid_item)
            self.window_list_widget.setItem(row, 2, process_item)
            self.window_list_widget.setItem(row, 3, x_item)
            self.window_list_widget.setItem(row, 4, y_item)
            self.window_list_widget.setItem(row, 5, width_item)
            self.window_list_widget.setItem(row, 6, height_item)
        
        # Re-enable sorting
        self.window_list_widget.setSortingEnabled(True)
        
        # Update count
        self.window_count_label.setText(f"창 {len(filtered_windows)}개")
    
    def apply_window_filters(self) -> List[WindowInfo]:
        """Apply current filters to window list."""
        filtered = self.window_list[:]
        
        # Apply search filter (if search input exists)
        if hasattr(self, 'search_input'):
            search_text = self.search_input.text().lower()
            if search_text:
                filtered = [w for w in filtered if 
                           search_text in w.title.lower() or 
                           search_text in w.process_name.lower()]
        
        # Apply category filter (if filter combo exists)
        if hasattr(self, 'filter_combo'):
            filter_type = self.filter_combo.currentText()
            if filter_type == "Visible Only" or filter_type == "보이는 창만":
                filtered = [w for w in filtered if w.is_visible and not w.is_minimized]
            elif filter_type == "Normal Windows" or filter_type == "일반 창":
                filtered = [w for w in filtered if w.is_visible and not w.is_minimized and not w.is_maximized]
            elif filter_type == "Browsers" or filter_type == "웹브라우저":
                browser_processes = {"chrome.exe", "firefox.exe", "msedge.exe", "opera.exe", "brave.exe"}
                filtered = [w for w in filtered if w.process_name.lower() in browser_processes]
            elif filter_type == "Games" or filter_type == "게임":
                # Simple heuristic for games
                filtered = [w for w in filtered if 
                           any(keyword in w.process_name.lower() for keyword in ["game", "steam", "epic"]) or
                           (w.rect.width >= 1024 and w.rect.height >= 768)]
        
        return filtered
    
    def filter_windows(self):
        """Apply filters and update display."""
        self.update_window_list_display()
    
    def on_window_selected(self):
        """Handle window selection (for QTableWidget)."""
        current_row = self.window_list_widget.currentRow()
        if current_row >= 0:
            # Get window info from first column (title column)
            title_item = self.window_list_widget.item(current_row, 0)
            if title_item:
                selected_data = title_item.data(Qt.UserRole)
                if selected_data:
                    # Handle both cases: full window object or just hwnd (int)
                    try:
                        import win32gui
                        
                        # Case 1: Full window object stored
                        if hasattr(selected_data, 'hwnd') and hasattr(selected_data, 'title'):
                            if win32gui.IsWindow(selected_data.hwnd):
                                self.current_window = selected_data
                                logger.info(f"Window selected: {self.current_window.title} (hwnd: {self.current_window.hwnd})")
                            else:
                                logger.warning(f"Selected window handle {selected_data.hwnd} is invalid")
                                self.current_window = None
                                return
                        # Case 2: Only hwnd (integer) stored - need to find full window object
                        elif isinstance(selected_data, int):
                            # Find the window object in cached windows
                            found_window = None
                            if hasattr(self, 'cached_windows') and self.cached_windows:
                                for window in self.cached_windows:
                                    if window.hwnd == selected_data:
                                        found_window = window
                                        break
                            
                            if found_window and win32gui.IsWindow(found_window.hwnd):
                                self.current_window = found_window
                                logger.info(f"Window selected: {self.current_window.title} (hwnd: {self.current_window.hwnd})")
                            else:
                                logger.warning(f"Window with handle {selected_data} not found or invalid")
                                self.current_window = None
                                return
                        else:
                            logger.error(f"Invalid window data type: {type(selected_data)}, value: {selected_data}")
                            self.current_window = None
                            return
                            
                    except Exception as e:
                        logger.warning(f"Error processing selected window: {e}")
                        self.current_window = None
                        return
                else:
                    self.current_window = None
                    logger.warning("Selected table item has no window data")
                    return
                    
                self.update_current_window_display()
                self.load_window_coordinates()
                
                # Enable controls
                self.enable_controls(True)
                
                # Enable coordinate control buttons
                if hasattr(self, 'add_to_profile_button'):
                    self.add_to_profile_button.setEnabled(True)
                if hasattr(self, 'get_coords_button'):
                    self.get_coords_button.setEnabled(True)
                if hasattr(self, 'apply_button'):
                    self.apply_button.setEnabled(True)
                if hasattr(self, 'center_button'):
                    self.center_button.setEnabled(True)
                if hasattr(self, 'save_profile_button'):
                    self.save_profile_button.setEnabled(True)
                
                # Enable preset buttons
                if hasattr(self, 'fhd_button'):
                    self.fhd_button.setEnabled(True)
                if hasattr(self, 'qhd_button'):
                    self.qhd_button.setEnabled(True)
                if hasattr(self, 'uhd_button'):
                    self.uhd_button.setEnabled(True)
                if hasattr(self, 'top_button'):
                    self.top_button.setEnabled(True)
                if hasattr(self, 'bottom_button'):
                    self.bottom_button.setEnabled(True)
                if hasattr(self, 'left_button'):
                    self.left_button.setEnabled(True)
                if hasattr(self, 'right_button'):
                    self.right_button.setEnabled(True)
                
                # Sync with preset controls
                if hasattr(self, 'preset_controls') and self.preset_controls:
                    self.preset_controls.set_selected_window(self.current_window.hwnd)
                
                # Update profile apply button state if profile is selected
                self.update_profile_apply_button()
        else:
            self.current_window = None
            logger.info("Window selection cleared - no current window")
            self.enable_controls(False)
            # Disable coordinate control buttons
            if hasattr(self, 'add_to_profile_button'):
                self.add_to_profile_button.setEnabled(False)
            if hasattr(self, 'get_coords_button'):
                self.get_coords_button.setEnabled(False)
            if hasattr(self, 'apply_button'):
                self.apply_button.setEnabled(False)
            if hasattr(self, 'center_button'):
                self.center_button.setEnabled(False)
            
            # Disable preset buttons
            if hasattr(self, 'fhd_button'):
                self.fhd_button.setEnabled(False)
            if hasattr(self, 'qhd_button'):
                self.qhd_button.setEnabled(False)
            if hasattr(self, 'uhd_button'):
                self.uhd_button.setEnabled(False)
            if hasattr(self, 'top_button'):
                self.top_button.setEnabled(False)
            if hasattr(self, 'bottom_button'):
                self.bottom_button.setEnabled(False)
            if hasattr(self, 'left_button'):
                self.left_button.setEnabled(False)
            if hasattr(self, 'right_button'):
                self.right_button.setEnabled(False)
            
            # Keep save_profile_button always enabled - function will show warning if needed
            
            # Update profile apply button state
            self.update_profile_apply_button()
    
    def update_current_window_display(self):
        """Update the current window information display."""
        if not self.current_window or not hasattr(self.current_window, 'title'):
            if hasattr(self, 'current_window_label'):
                self.current_window_label.setText("선택하지 않음")
            # Clear invalid current_window
            if self.current_window and not hasattr(self.current_window, 'title'):
                logger.error(f"Invalid current_window object: {type(self.current_window)}, clearing")
                self.current_window = None
            return
        
        # Update current window label (new UI)
        if hasattr(self, 'current_window_label'):
            display_text = f"{self.current_window.title} ({self.current_window.process_name})"
            if len(display_text) > 60:  # Truncate if too long
                display_text = display_text[:57] + "..."
            self.current_window_label.setText(display_text)
        
        # Window info labels removed per user request
        
        # Window state label removed per user request
    
    def load_window_coordinates(self):
        """Load current window coordinates into input fields (if they exist)."""
        if not self.current_window:
            return
        
        rect = self.current_window.rect
        
        # Only update spinboxes if they exist
        if hasattr(self, 'x_spinbox'):
            self.x_spinbox.setValue(rect.left)
        if hasattr(self, 'y_spinbox'):
            self.y_spinbox.setValue(rect.top)
        if hasattr(self, 'width_spinbox'):
            self.width_spinbox.setValue(rect.width)
        if hasattr(self, 'height_spinbox'):
            self.height_spinbox.setValue(rect.height)
    
    def enable_controls(self, enabled: bool):
        """Enable or disable control buttons."""
        # Only enable buttons that actually exist
        button_names = [
            'apply_button', 'center_button', 'minimize_button',
            'maximize_button', 'restore_button', 'snap_left_button',
            'snap_right_button', 'snap_top_button', 'snap_bottom_button',
            'size_1024_button', 'size_1280_button',
            'pos_up_button', 'pos_down_button', 'pos_left_button', 'pos_right_button',
            'fhd_button', 'qhd_button', 'uhd_button'
        ]
        
        for button_name in button_names:
            if hasattr(self, button_name):
                getattr(self, button_name).setEnabled(enabled)
        
        # Also enable/disable coordinate inputs (if they exist)
        input_names = ['x_spinbox', 'y_spinbox', 'width_spinbox', 'height_spinbox']
        for input_name in input_names:
            if hasattr(self, input_name):
                getattr(self, input_name).setEnabled(enabled)
    
    def auto_refresh_windows(self):
        """Auto-refresh window list if enabled."""
        if hasattr(self, 'auto_refresh_checkbox') and self.auto_refresh_checkbox.isChecked():
            self.refresh_window_list()
    
    def toggle_auto_refresh(self, enabled: bool):
        """Toggle auto-refresh timer."""
        if enabled:
            self.auto_refresh_timer.start()
        else:
            self.auto_refresh_timer.stop()
    
    def toggle_realtime_coordinates(self, enabled: bool):
        """Toggle real-time coordinate updates."""
        if enabled:
            self.coordinate_timer.start()
        else:
            self.coordinate_timer.stop()
    
    def update_current_window_coordinates(self):
        """Update coordinates of current window in real-time."""
        if not self.current_window or not self.realtime_update_checkbox.isChecked():
            return
        
        try:
            # Get fresh window info
            info_result = self.window_manipulator.safe_get_window_info(self.current_window.hwnd)
            
            if info_result.get("success"):
                info = info_result["info"]
                rect = info["rect"]
                
                if rect:
                    # Update spinboxes without triggering signals (if they exist)
                    if hasattr(self, 'x_spinbox'):
                        self.x_spinbox.blockSignals(True)
                        self.x_spinbox.setValue(rect.left)
                        self.x_spinbox.blockSignals(False)
                    if hasattr(self, 'y_spinbox'):
                        self.y_spinbox.blockSignals(True)
                        self.y_spinbox.setValue(rect.top)
                        self.y_spinbox.blockSignals(False)
                    if hasattr(self, 'width_spinbox'):
                        self.width_spinbox.blockSignals(True)
                        self.width_spinbox.setValue(rect.width)
                        self.width_spinbox.blockSignals(False)
                    if hasattr(self, 'height_spinbox'):
                        self.height_spinbox.blockSignals(True)
                        self.height_spinbox.setValue(rect.height)
                        self.height_spinbox.blockSignals(False)
                    
                    # Update current window info
                    self.current_window.rect = rect
        
        except Exception as e:
            logger.debug(f"Error updating coordinates: {e}")
    
    def apply_coordinates(self):
        """Apply current coordinates to selected window with enhanced game engine support."""
        if not self.current_window:
            self.show_themed_warning("경고", "먼저 창을 선택하세요.")
            return
        
        # Get coordinates from spinboxes if they exist, otherwise use current window rect
        if hasattr(self, 'x_spinbox') and hasattr(self, 'y_spinbox') and hasattr(self, 'width_spinbox') and hasattr(self, 'height_spinbox'):
            x = self.x_spinbox.value()
            y = self.y_spinbox.value()
            width = self.width_spinbox.value()
            height = self.height_spinbox.value()
        else:
            # Fallback to current window coordinates
            rect = self.current_window.rect
            x, y, width, height = rect.left, rect.top, rect.width, rect.height
        
        hwnd = self.current_window.hwnd
        
        self.status_label.setText("게임 엔진 감지 및 좌표 적용 중...")
        
        try:
            # Use enhanced window manipulation with game engine detection
            success = self.window_manipulator.move_window_enhanced(hwnd, x, y, width, height)
            
            if success:
                self.status_label.setText(f"창 위치 및 크기 적용됨: ({x}, {y}) {width}x{height}")
                
                # 원본 좌표 저장 (갱신 여부 판단용)
                original_rect = self.current_window.rect
                
                # 적용 후 실제 창의 좌표를 다시 가져와서 스피너 박스에 반영
                try:
                    from core.windows_api import WindowsAPI, WindowRect
                    api = WindowsAPI()
                    actual_rect = api.get_window_rect(hwnd)
                    
                    if actual_rect:
                        # Update current window info with actual coordinates
                        self.current_window.rect = actual_rect
                        
                        # 스피너 박스가 존재하면 실제 좌표로 업데이트
                        if hasattr(self, 'x_spinbox'):
                            self.x_spinbox.setValue(actual_rect.left)
                        if hasattr(self, 'y_spinbox'):
                            self.y_spinbox.setValue(actual_rect.top)
                        if hasattr(self, 'width_spinbox'):
                            self.width_spinbox.setValue(actual_rect.width)
                        if hasattr(self, 'height_spinbox'):
                            self.height_spinbox.setValue(actual_rect.height)
                        
                        # 원래 활성 창 목록의 값과 다른지 확인하여 필요시에만 갱신
                        if (actual_rect.left != original_rect.left or 
                            actual_rect.top != original_rect.top or 
                            actual_rect.width != original_rect.width or 
                            actual_rect.height != original_rect.height):
                            # 스피너 박스 값이 원래 창 목록 값과 다르므로 목록 갱신
                            QTimer.singleShot(500, self.refresh_window_list)
                            logger.info("Window list refreshed due to coordinate changes")
                        else:
                            logger.info("No coordinate changes detected, skipping window list refresh")
                        
                        logger.info(f"Updated coordinates after apply: {actual_rect}")
                    else:
                        # 좌표를 가져올 수 없는 경우 기본적으로 목록 갱신
                        from core.windows_api import WindowRect
                        self.current_window.rect = WindowRect(x, y, x + width, y + height)
                        QTimer.singleShot(500, self.refresh_window_list)
                        logger.warning("Could not get actual coordinates, using applied coordinates and refreshing list")
                except Exception as coord_error:
                    logger.warning(f"Failed to update coordinates after apply: {coord_error}")
                    # 오류 발생 시 기본적으로 목록 새로고침
                    from core.windows_api import WindowRect
                    self.current_window.rect = WindowRect(x, y, x + width, y + height)
                    QTimer.singleShot(500, self.refresh_window_list)
            else:
                # Try to get engine info for better error message
                try:
                    engine_info = self.window_manipulator.detect_game_engine(hwnd)
                    QMessageBox.warning(
                        self, "창 조작 실패", 
                        f"창 위치 변경에 실패했습니다.\n\n"
                        f"감지된 엔진: {engine_info.engine_type}\n"
                        f"특수 처리 필요: {'예' if engine_info.requires_special_handling else '아니오'}\n"
                        f"크기 조정 지원: {'예' if engine_info.supports_resize else '아니오'}\n"
                        f"이동 지원: {'예' if engine_info.supports_move else '아니오'}\n\n"
                        f"일부 게임은 창모드를 지원하지 않거나 관리자 권한이 필요할 수 있습니다."
                    )
                except Exception:
                    self.show_themed_warning("오류", "창 위치를 변경할 수 없습니다.")
                
                self.status_label.setText("창 조작 실패")
        
        except Exception as e:
            logger.error(f"Error applying coordinates: {e}")
            self.status_label.setText(f"오류: {str(e)}")
            self.show_themed_critical("오류", f"좌표 적용 중 오류 발생:\n{str(e)}")
    
    def center_window(self):
        """Center the selected window with enhanced game engine support."""
        if not self.current_window:
            self.show_themed_warning("경고", "먼저 창을 선택하세요.")
            return
        
        self.status_label.setText("창을 화면 중앙으로 이동 중...")
        
        try:
            success = self.window_manipulator.center_window(self.current_window.hwnd)
            
            if success:
                self.status_label.setText("창이 화면 중앙으로 이동되었습니다")
                # Refresh coordinates to show new position
                self.load_window_coordinates()
                # Refresh window list
                QTimer.singleShot(300, self.refresh_window_list)
            else:
                self.status_label.setText("창 중앙 이동 실패")
                self.show_themed_warning("오류", "창을 중앙으로 이동할 수 없습니다.")
        
        except Exception as e:
            logger.error(f"Error centering window: {e}")
            self.status_label.setText(f"오류: {str(e)}")
            self.show_themed_critical("오류", f"창 중앙 이동 중 오류 발생:\n{str(e)}")
    
    def set_resolution_preset(self, width: int, height: int):
        """Set resolution preset and apply to selected window."""
        if not self.current_window:
            self.show_themed_warning("경고", "먼저 창을 선택하세요.")
            return
        
        # Update spinboxes if they exist
        if hasattr(self, 'width_spinbox'):
            self.width_spinbox.setValue(width)
        if hasattr(self, 'height_spinbox'):
            self.height_spinbox.setValue(height)
        
        # Apply immediately
        try:
            success = self.window_manipulator.resize_window(
                self.current_window.hwnd, width, height
            )
            
            if success:
                self.status_label.setText(f"창 크기를 {width}x{height}로 변경했습니다")
                self.load_window_coordinates()
                QTimer.singleShot(300, self.refresh_window_list)
            else:
                self.status_label.setText("창 크기 변경 실패")
                self.show_themed_warning("오류", f"창 크기를 {width}x{height}로 변경할 수 없습니다.")
        
        except Exception as e:
            logger.error(f"Error setting resolution: {e}")
            self.status_label.setText(f"오류: {str(e)}")
    
    def set_position_preset(self, position: str):
        """Set position preset and apply to selected window."""
        if not self.current_window:
            self.show_themed_warning("경고", "먼저 창을 선택하세요.")
            return
        
        try:
            current_width = getattr(self, 'width_spinbox', None)
            current_height = getattr(self, 'height_spinbox', None)
            window_width = current_width.value() if current_width else 800
            window_height = current_height.value() if current_height else 600
            work_area = self.get_work_area_for_window(self.current_window.hwnd)
            x, y = self.calculate_position_in_work_area(
                position, window_width, window_height, work_area
            )
            
            # Update spinboxes if they exist
            if hasattr(self, 'x_spinbox'):
                self.x_spinbox.setValue(x)
            if hasattr(self, 'y_spinbox'):
                self.y_spinbox.setValue(y)
            
            # Apply immediately
            success = self.window_manipulator.move_window(
                self.current_window.hwnd, x, y, window_width, window_height
            )
            
            if success:
                self.status_label.setText(f"창을 {position} 위치로 이동했습니다")
                self.load_window_coordinates()
                QTimer.singleShot(300, self.refresh_window_list)
            else:
                self.status_label.setText(f"{position} 위치 이동 실패")
                self.show_themed_warning("오류", f"창을 {position} 위치로 이동할 수 없습니다.")
        
        except Exception as e:
            logger.error(f"Error setting {position} position: {e}")
            self.status_label.setText(f"오류: {str(e)}")
    
    def get_current_coordinates(self):
        """Get current coordinates of selected window and update input fields."""
        if not self.current_window:
            self.show_themed_warning("경고", "먼저 창을 선택해주세요.")
            return
        
        try:
            # Get current window rectangle
            from core.windows_api import WindowsAPI
            api = WindowsAPI()
            rect = api.get_window_rect(self.current_window.hwnd)
            
            if rect:
                # Update coordinate input fields if they exist
                if hasattr(self, 'x_spinbox'):
                    self.x_spinbox.setValue(rect.left)
                if hasattr(self, 'y_spinbox'):
                    self.y_spinbox.setValue(rect.top)
                if hasattr(self, 'width_spinbox'):
                    self.width_spinbox.setValue(rect.width)
                if hasattr(self, 'height_spinbox'):
                    self.height_spinbox.setValue(rect.height)
                
                self.status_label.setText("현재 창의 좌표를 성공적으로 가져왔습니다")
                logger.info(f"Retrieved coordinates for window '{self.current_window.title}': {rect}")
            else:
                self.show_themed_warning("오류", "창의 좌표를 가져올 수 없습니다.")
                
        except Exception as e:
            logger.error(f"Error getting current coordinates: {str(e)}")
            self.show_themed_critical("오류", f"좌표 가져오기 중 오류가 발생했습니다:\n{str(e)}")
            self.status_label.setText(f"오류: {str(e)}")
    
    def minimize_window(self):
        """Minimize the selected window."""
        if not self.current_window:
            return
        
        try:
            result = self.window_manipulator.enhanced_minimize_window(self.current_window.hwnd)
            
            if result.success:
                self.status_label.setText("Window minimized")
                self.current_window.is_minimized = True
                self.update_current_window_display()
            else:
                error_msg = result.error_info.get('message', 'Unknown error') if result.error_info else 'Unknown error'
                self.show_themed_warning("Operation Failed", f"Could not minimize window:\n{error_msg}")
        
        except Exception as e:
            self.show_themed_critical("Error", f"An error occurred:\n{str(e)}")
    
    def maximize_window(self):
        """Maximize the selected window."""
        if not self.current_window:
            return
        
        try:
            result = self.window_manipulator.enhanced_maximize_window(self.current_window.hwnd)
            
            if result.success:
                self.status_label.setText("Window maximized")
                self.current_window.is_maximized = True
                self.update_current_window_display()
            else:
                error_msg = result.error_info.get('message', 'Unknown error') if result.error_info else 'Unknown error'
                self.show_themed_warning("Operation Failed", f"Could not maximize window:\n{error_msg}")
        
        except Exception as e:
            self.show_themed_critical("Error", f"An error occurred:\n{str(e)}")
    
    def restore_window(self):
        """Restore the selected window."""
        if not self.current_window:
            return
        
        try:
            result = self.window_manipulator.enhanced_restore_window(self.current_window.hwnd)
            
            if result.success:
                self.status_label.setText("Window restored")
                self.current_window.is_minimized = False
                self.current_window.is_maximized = False
                self.update_current_window_display()
                self.load_window_coordinates()
            else:
                error_msg = result.error_info.get('message', 'Unknown error') if result.error_info else 'Unknown error'
                self.show_themed_warning("Operation Failed", f"Could not restore window:\n{error_msg}")
        
        except Exception as e:
            self.show_themed_critical("Error", f"An error occurred:\n{str(e)}")
    
    def snap_window(self, direction: str):
        """Snap window to screen edge."""
        if not self.current_window:
            return
        
        try:
            result = self.window_manipulator.enhanced_snap_to_edge(self.current_window.hwnd, direction)
            
            if result.success:
                self.status_label.setText(f"Window snapped to {direction}")
                self.load_window_coordinates()
            else:
                error_msg = result.error_info.get('message', 'Unknown error') if result.error_info else 'Unknown error'
                QMessageBox.warning(self, "Operation Failed", f"Could not snap window:\n{error_msg}")
        
        except Exception as e:
            self.show_themed_critical("Error", f"An error occurred:\n{str(e)}")
    
    def resize_window_to(self, width: int, height: int):
        """Resize window to specific dimensions."""
        if not self.current_window:
            return
        
        try:
            result = self.window_manipulator.enhanced_resize_window(
                self.current_window.hwnd, width, height
            )
            
            if result.success:
                self.status_label.setText(f"Window resized to {width}×{height}")
                self.load_window_coordinates()
            else:
                error_msg = result.error_info.get('message', 'Unknown error') if result.error_info else 'Unknown error'
                QMessageBox.warning(self, "Operation Failed", f"Could not resize window:\n{error_msg}")
        
        except Exception as e:
            self.show_themed_critical("Error", f"An error occurred:\n{str(e)}")
    
    def toggle_safe_mode(self, enabled: bool):
        """Toggle safe mode."""
        if enabled:
            self.window_manipulator.enable_safe_mode()
            self.status_label.setText("Safe mode enabled")
            self.connection_label.setText("API: Safe Mode")
            self.connection_label.setStyleSheet("")  # Use theme colors
        else:
            self.window_manipulator.disable_safe_mode()
            self.status_label.setText("Safe mode disabled")
            self.connection_label.setText("API: Connected")
            self.connection_label.setStyleSheet("")  # Use theme colors
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(self, "About WindowResizer", 
                         "WindowResizer v0.01.4\n\n"
                         "Advanced window management tool with comprehensive error handling.\n\n"
                         "Features:\n"
                         "• Window enumeration and manipulation\n"
                         "• Real-time coordinate tracking\n"
                         "• Multi-monitor support\n"
                         "• Application compatibility testing\n"
                         "• Robust error recovery\n\n"
                         "Built with PyQt5 and Windows API integration.")
    
    def show_profile_manager(self):
        """Show the profile manager dialog."""
        try:
            if self.profile_manager_dialog is None:
                self.profile_manager_dialog = ProfileManagerDialog(self)
                self.profile_manager_dialog.profile_applied.connect(self.on_profile_applied)
            
            # Set current window info for profile operations
            if self.current_window:
                window_info = self.get_current_window_info()
                self.profile_manager_dialog.set_current_window_info(window_info)
            
            self.profile_manager_dialog.show()
            self.profile_manager_dialog.raise_()
            self.profile_manager_dialog.activateWindow()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open profile manager:\n{str(e)}")
    
    def save_current_as_profile(self):
        """Save current window configuration as a new profile."""
        if not self.current_window:
            self.show_themed_warning("Warning", "Please select a window first.")
            return
        
        try:
            window_info = self.get_current_window_info()
            dialog = ProfileEditDialog(self, window_info=window_info)
            
            if dialog.exec_() == dialog.Accepted:
                data = dialog.get_profile_data()
                profile = self.profile_manager.create_profile(**data)
                
                self.show_themed_information("Success", 
                                      f"Profile '{profile.name}' created successfully!")
                self.status_label.setText(f"Profile '{profile.name}' saved")
                
        except Exception as e:
            self.show_themed_critical("Error", f"Failed to save profile:\n{str(e)}")
    
    def apply_profile_to_current(self):
        """Apply a profile to the currently selected window."""
        if not self.current_window:
            QMessageBox.warning(self, "Warning", "Please select a window first.")
            return
        
        try:
            # Show profile manager for selection
            self.show_profile_manager()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply profile:\n{str(e)}")
    
    def auto_apply_profiles(self):
        """Auto-apply all matching profiles to current windows."""
        # Window enumeration is asynchronous. Apply only after the refreshed
        # list arrives so a single click includes newly opened windows.
        try:
            self.refresh_window_list(self._apply_all_profiles_to_windows)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로필 자동 적용 실패:\n{str(e)}")

    def _apply_all_profiles_to_windows(self, windows: List[WindowInfo]):
        """Apply every matching profile to a freshly enumerated window list."""
        try:
            # Get all current windows and validate handles
            windows_info = []
            for window in windows:
                # Validate window handle before processing
                try:
                    import win32gui
                    if not win32gui.IsWindow(window.hwnd):
                        logger.warning(f"Skipping invalid window handle: {window.hwnd} ({window.title})")
                        continue
                except Exception as e:
                    logger.warning(f"Cannot validate window handle {window.hwnd}: {e}")
                    continue
                    
                window_info = {
                    'hwnd': window.hwnd,
                    'title': window.title,
                    'process_name': window.process_name,
                    'pid': window.pid,
                    'executable_path': window.executable_path,
                    'rect': window.rect,
                    'is_maximized': window.is_maximized,
                    'is_minimized': window.is_minimized,
                    'is_visible': window.is_visible,
                }
                windows_info.append(window_info)
            
            # Apply all profiles (전체 적용 버튼용)
            results = self.profile_manager.apply_all_profiles(windows_info)
            
            applied_count = len(results.get('applied', []))
            failed_count = len(results.get('failed', []))
            
            if applied_count > 0:
                message = f"성공적으로 {applied_count}개의 프로필이 적용되었습니다"
                if failed_count > 0:
                    message += f", {failed_count}개 실패"
                # 알림창 대신 콘솔 로그와 소리 알림 사용
                logger.info(f"프로필 자동 적용 완료: {message}")
                self.status_label.setText(f"{applied_count}개 프로필 자동 적용됨")
                # 소리 알림 비활성화 (사용자 요청)
                # try:
                #     import winsound
                #     winsound.Beep(800, 200)  # 성공 알림음
                # except:
                #     pass
            else:
                logger.info("프로필 자동 적용: 현재 실행중인 창에 일치하는 프로필이 없습니다")
                self.status_label.setText("적용할 프로필이 없음")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로필 자동 적용 실패:\n{str(e)}")
    
    def on_profile_applied(self, profile_id: str, window_info: Dict[str, Any]):
        """Handle profile application from profile manager."""
        try:
            # Refresh window list to show changes
            self.refresh_window_list()
            self.status_label.setText(f"Profile applied to window")
            
        except Exception as e:
            logger.error(f"Error handling profile application: {e}")
    
    def show_search_dialog(self):
        """Show search and filter dialog."""
        QMessageBox.information(self, "검색 및 필터", 
                               "검색 및 필터 기능은 향후 별도 다이얼로그로 제공될 예정입니다.\n"
                               "현재는 레이아웃 공간 확보를 위해 임시 제거되었습니다.")
    
    def show_coords_dialog(self):
        """Show coordinates adjustment dialog."""
        QMessageBox.information(self, "좌표 조정", 
                               "창 크기 및 위치 조정 기능은 향후 별도 다이얼로그로 제공될 예정입니다.\n"
                               "현재는 레이아웃 공간 확보를 위해 임시 제거되었습니다.")
    
    def show_auto_apply_dialog(self):
        """Show auto-apply settings dialog."""
        QMessageBox.information(self, "자동 적용 설정", 
                               "자동 프로필 적용 설정 기능은 향후 별도 다이얼로그로 제공될 예정입니다.\n"
                               "현재는 레이아웃 공간 확보를 위해 임시 제거되었습니다.")
    
    def get_current_window_info(self) -> Dict[str, Any]:
        """Get current window information for profile operations."""
        if not self.current_window:
            return {}
        
        return {
            'hwnd': self.current_window.hwnd,
            'title': self.current_window.title,
            'process_name': self.current_window.process_name,
            'executable_path': self.current_window.executable_path,
            'rect': self.current_window.rect,
            'is_maximized': self.current_window.is_maximized,
            'is_minimized': self.current_window.is_minimized,
            'is_visible': self.current_window.is_visible
        }
    
    def on_preset_applied(self, name: str, width: int, height: int, hwnd: int):
        """Handle preset application from preset controls."""
        try:
            # Use current window if hwnd is 0
            target_hwnd = hwnd if hwnd else (self.current_window.hwnd if self.current_window else 0)
            
            if not target_hwnd:
                self.show_themed_warning("경고", "먼저 창을 선택해주세요.")
                return
            
            # Update position & size controls with preset values if they exist
            if hasattr(self, 'x_spinbox') and hasattr(self, 'y_spinbox'):
                current_x = self.x_spinbox.value()
                current_y = self.y_spinbox.value()
            else:
                # Use current window coordinates
                current_x = self.current_window.rect.left if self.current_window else 0
                current_y = self.current_window.rect.top if self.current_window else 0
            
            if hasattr(self, 'width_spinbox'):
                self.width_spinbox.setValue(width)
            if hasattr(self, 'height_spinbox'):
                self.height_spinbox.setValue(height)
            
            # Apply the preset using window manipulator
            result = self.window_manipulator.enhanced_move_window(
                target_hwnd, current_x, current_y, width, height
            )
            success = result.success
            
            if success:
                self.status_label.setText(f"프리셋 '{name}' ({width}×{height})을 적용했습니다")
                self.update_current_window_display()  # Update coordinate display
                
                # 프리셋 적용 후 실제 창의 좌표를 다시 가져와서 스피너 박스에 반영
                try:
                    from core.windows_api import WindowsAPI
                    api = WindowsAPI()
                    rect = api.get_window_rect(target_hwnd)
                    
                    if rect:
                        # 스피너 박스가 존재하면 실제 좌표로 업데이트
                        if hasattr(self, 'x_spinbox'):
                            self.x_spinbox.setValue(rect.left)
                        if hasattr(self, 'y_spinbox'):
                            self.y_spinbox.setValue(rect.top)
                        if hasattr(self, 'width_spinbox'):
                            self.width_spinbox.setValue(rect.width)
                        if hasattr(self, 'height_spinbox'):
                            self.height_spinbox.setValue(rect.height)
                        
                        logger.info(f"Updated spinboxes with actual coordinates after preset application: {rect}")
                except Exception as coord_error:
                    logger.warning(f"Failed to update coordinates after preset application: {coord_error}")
            else:
                self.show_themed_warning("경고", f"프리셋 '{name}' 적용에 실패했습니다")
                
        except Exception as e:
            logger.error(f"Error applying preset: {e}")
            self.show_themed_critical("오류", f"프리셋 적용 중 오류가 발생했습니다:\n{str(e)}")
    
    def on_preset_selected(self, name: str, width: int, height: int):
        """Handle preset selection from preset controls (sync with position & size)."""
        try:
            # Update width and height in position & size controls if they exist
            if hasattr(self, 'width_spinbox'):
                self.width_spinbox.setValue(width)
            if hasattr(self, 'height_spinbox'):
                self.height_spinbox.setValue(height)
            
            self.status_label.setText(f"프리셋 '{name}' ({width}×{height})을 위치 및 크기에 적용했습니다")
            
        except Exception as e:
            logger.error(f"Error syncing preset selection: {e}")
    
    def on_preset_window_selected(self, hwnd: int):
        """Handle window selection from preset controls."""
        try:
            # Find the window in our list and select it
            for row in range(self.window_list_widget.rowCount()):
                title_item = self.window_list_widget.item(row, 0)
                if title_item:
                    item_data = title_item.data(Qt.UserRole)
                    # Handle both window object and hwnd cases
                    item_hwnd = None
                    if hasattr(item_data, 'hwnd'):
                        item_hwnd = item_data.hwnd
                    elif isinstance(item_data, int):
                        item_hwnd = item_data
                    
                    if item_hwnd == hwnd:
                        self.window_list_widget.selectRow(row)
                        break
            
        except Exception as e:
            logger.error(f"Error selecting window from preset controls: {e}")
    
    def on_theme_changed(self, theme_name: str):
        """Handle theme changes."""
        try:
            self.status_label.setText(f"Theme changed to: {theme_name}")
            logger.info(f"Theme changed to: {theme_name}")
        except Exception as e:
            logger.error(f"Error handling theme change: {e}")
    
    def refresh_profile_list(self):
        """Refresh the profile dropdown list."""
        try:
            if not hasattr(self, 'profile_combo'):
                return  # Profile combo not available in current layout
                
            self.profile_combo.clear()
            self.profile_combo.addItem("새 프로필...")
            
            # Add existing profiles
            profiles = self.profile_manager.list_profiles()
            for profile in profiles:
                self.profile_combo.addItem(profile.name, profile.id)
                
        except Exception as e:
            logger.error(f"Error refreshing profile list: {e}")
    
    def on_profile_selection_changed(self, profile_name: str):
        """Handle profile selection change."""
        try:
            if profile_name == "새 프로필...":
                self.update_profile_button.setEnabled(False)
                self.load_profile_button.setText("새로 생성")
            else:
                self.update_profile_button.setEnabled(True)
                self.load_profile_button.setText("불러오기")
                
        except Exception as e:
            logger.error(f"Error handling profile selection change: {e}")
    
    def on_profile_selected(self, *args):
        """Handle profile table selection change."""
        try:
            if not hasattr(self, 'profile_table_widget'):
                return
                
            selected_items = self.profile_table_widget.selectedItems()
            has_selection = len(selected_items) > 0
            has_current_window = self.current_window is not None
            
            # Debug logging
            logger.info(f"Profile selection changed:")
            logger.info(f"  - Selected items: {len(selected_items)}")
            logger.info(f"  - Has current window: {has_current_window}")
            logger.info(f"  - Current window: {self.current_window.title if self.current_window else 'None'}")
            
            # Enable/disable profile management buttons based on selection
            if hasattr(self, 'edit_profile_button'):
                self.edit_profile_button.setEnabled(has_selection)
            if hasattr(self, 'delete_profile_button'):
                self.delete_profile_button.setEnabled(has_selection)
            if hasattr(self, 'apply_profile_button'):
                # 프로필 선택만으로도 적용 버튼 활성화 (창은 나중에 선택해도 됨)
                self.apply_profile_button.setEnabled(has_selection)
                logger.info(f"Apply button enabled: {has_selection}")
            if hasattr(self, 'profile_preview_button'):
                self.profile_preview_button.setEnabled(has_selection)
                
        except Exception as e:
            logger.error(f"Error handling profile table selection: {e}")
    
    def update_profile_apply_button(self):
        """Update profile apply button state based on current selections."""
        try:
            if not hasattr(self, 'apply_profile_button'):
                return
                
            # Check if profile is selected
            has_profile_selection = False
            if hasattr(self, 'profile_table_widget'):
                selected_items = self.profile_table_widget.selectedItems()
                has_profile_selection = len(selected_items) > 0
            
            # Enable if profile is selected (window selection will be checked when apply is clicked)
            self.apply_profile_button.setEnabled(has_profile_selection)
            
        except Exception as e:
            logger.error(f"Error updating profile apply button: {e}")
    
    def restore_window_selection(self, hwnd: int):
        """Restore window selection after list update."""
        try:
            for row in range(self.window_list_widget.rowCount()):
                title_item = self.window_list_widget.item(row, 0)
                if title_item:
                    window_data = title_item.data(Qt.UserRole)
                    if window_data:
                        # Handle both window object and hwnd cases
                        window_hwnd = None
                        if hasattr(window_data, 'hwnd'):
                            window_hwnd = window_data.hwnd
                        elif isinstance(window_data, int):
                            window_hwnd = window_data
                        
                        if window_hwnd == hwnd:
                            self.window_list_widget.selectRow(row)
                            # Set current_window appropriately
                            if hasattr(window_data, 'hwnd') and hasattr(window_data, 'title'):
                                self.current_window = window_data
                                logger.info(f"Restored selection for window: {window_data.title}")
                            else:
                                # Need to find full window object
                                if hasattr(self, 'cached_windows') and self.cached_windows:
                                    for window in self.cached_windows:
                                        if window.hwnd == hwnd:
                                            self.current_window = window
                                            logger.info(f"Restored selection for window: {window.title}")
                                            break
                            return
            
            # Window no longer exists, clear selection
            logger.info("Previously selected window no longer exists, clearing selection")
            self.current_window = None
            
        except Exception as e:
            logger.error(f"Error restoring window selection: {e}")
    
    def on_profile_double_clicked(self, item):
        """Handle double-click on profile table to open editor."""
        try:
            if not item:
                return
            
            # Get the profile from the double-clicked row
            current_row = item.row()
            if current_row < 0:
                return
            
            # Set the selection to ensure get_selected_profile works
            self.profile_table_widget.selectRow(current_row)
            
            # Open the profile editor
            self.edit_selected_profile()
            
        except Exception as e:
            logger.error(f"Error handling profile double-click: {e}")
    
    def get_selected_profile(self):
        """Get the currently selected profile from the table."""
        try:
            if not hasattr(self, 'profile_table_widget'):
                return None
                
            current_row = self.profile_table_widget.currentRow()
            if current_row < 0:
                return None
                
            # Get profile ID from the first column
            id_item = self.profile_table_widget.item(current_row, 0)
            if not id_item:
                return None
                
            profile_id = id_item.data(Qt.UserRole)
            if not profile_id:
                return None
                
            # Find profile by ID
            profiles = self.profile_manager.list_profiles()
            for profile in profiles:
                if profile.id == profile_id:
                    return profile
                    
            return None
            
        except Exception as e:
            logger.error(f"Error getting selected profile: {e}")
            return None
    
    def edit_selected_profile(self):
        """Edit the selected profile using the comprehensive profile editor."""
        try:
            profile = self.get_selected_profile()
            if not profile:
                self.show_themed_warning("경고", "편집할 프로필을 선택해주세요.")
                return
                
            # Open comprehensive profile edit dialog
            dialog = ProfileEditorDialog(profile=profile, parent=self)
            dialog.profile_saved.connect(self.on_profile_updated)
            
            if dialog.exec_() == dialog.Accepted:
                self.status_label.setText(f"프로필 '{profile.name}'이 수정되었습니다")
                
        except Exception as e:
            logger.error(f"Error editing profile: {e}")
            self.show_themed_critical("오류", f"프로필 편집 중 오류가 발생했습니다:\n{str(e)}")
    
    def on_profile_updated(self, profile_data: dict):
        """Handle profile update from the editor dialog."""
        try:
            from core.profile_manager import ProfileType, MatchingStrategy, WindowConfiguration, MatchingCriteria
            
            # Get the current profile to update
            current_profile = self.get_selected_profile()
            if not current_profile:
                logger.error("No profile selected for update")
                return
            
            # Update basic info
            current_profile.name = profile_data['name']
            current_profile.description = profile_data['description']
            current_profile.auto_apply = profile_data['auto_apply']
            current_profile.enabled = profile_data['enabled']
            
            # Update advanced features
            hotkey_data = profile_data.get('hotkey')
            if hotkey_data is None:
                hotkey_data = profile_data
            current_profile.hotkey_enabled = hotkey_data.get(
                'enabled', hotkey_data.get('hotkey_enabled', False)
            )
            current_profile.hotkey_combination = hotkey_data.get(
                'combination', hotkey_data.get('hotkey_combination', '')
            )
            current_profile.hotkey_action = hotkey_data.get(
                'action', hotkey_data.get('hotkey_action', 'apply_profile')
            )
            
            advanced_data = profile_data.get('advanced_features')
            if advanced_data is None:
                advanced_data = profile_data
            current_profile.lock_size = advanced_data.get(
                'lock_size', current_profile.lock_size
            )
            current_profile.lock_width = advanced_data.get(
                'lock_width', current_profile.lock_width
            )
            current_profile.lock_height = advanced_data.get(
                'lock_height', current_profile.lock_height
            )
            current_profile.lock_position = advanced_data.get(
                'lock_position', current_profile.lock_position
            )
            current_profile.mouse_constraint = advanced_data.get(
                'mouse_constraint', current_profile.mouse_constraint
            )
            current_profile.constraint_mode = advanced_data.get(
                'constraint_mode', current_profile.constraint_mode
            )
            current_profile.constraint_escape_key = advanced_data.get(
                'constraint_escape_key', current_profile.constraint_escape_key
            )
            
            # Update window configuration
            window_config_data = profile_data['window_config']
            current_profile.window_config = WindowConfiguration(
                x=window_config_data['x'],
                y=window_config_data['y'],
                width=window_config_data['width'],
                height=window_config_data['height'],
                is_maximized=window_config_data['is_maximized'],
                is_minimized=window_config_data['is_minimized'],
                always_on_top=window_config_data['always_on_top'],
                opacity=window_config_data['opacity'],
                monitor_index=window_config_data['monitor_index']
            )
            
            # Update matching criteria
            criteria_data = profile_data['matching_criteria']
            strategy_mapping = {
                'title_contains': MatchingStrategy.TITLE_CONTAINS,
                'exact_title': MatchingStrategy.EXACT_TITLE,
                'title_regex': MatchingStrategy.TITLE_REGEX,
                'process_name': MatchingStrategy.PROCESS_NAME,
                'executable_path': MatchingStrategy.EXECUTABLE_PATH,
                'combined': MatchingStrategy.COMBINED
            }
            
            current_profile.matching_criteria = MatchingCriteria(
                strategy=strategy_mapping[criteria_data['strategy']],
                window_title_pattern=criteria_data['window_title_pattern'],
                process_name_pattern=criteria_data['process_name_pattern'],
                executable_path_pattern=criteria_data.get('executable_path_pattern', ''),
                case_sensitive=criteria_data['case_sensitive'],
                priority=criteria_data['priority']
            )
            
            # Update timestamp
            current_profile.modified_at = time.time()
            
            # Save the updated profile
            default_profile_manager.save_profiles()
            
            # Force refresh the profile table to show updated values
            self.refresh_profile_table()
            
            # Refresh profile list if it exists
            if hasattr(self, 'refresh_profile_list'):
                self.refresh_profile_list()
            
            # Clear selection and reselect the updated profile
            QTimer.singleShot(100, lambda: self._reselect_profile(current_profile.id))
            
            logger.info(f"Profile '{current_profile.name}' updated successfully")
            
        except Exception as e:
            logger.error(f"Error updating profile: {e}")
            QMessageBox.critical(self, "프로필 업데이트 오류", f"프로필 업데이트 중 오류가 발생했습니다: {str(e)}")
    
    def _reselect_profile(self, profile_id: str):
        """Reselect a profile in the table by its ID."""
        try:
            for row in range(self.profile_table_widget.rowCount()):
                item = self.profile_table_widget.item(row, 0)
                if item and item.data(Qt.UserRole) == profile_id:
                    self.profile_table_widget.selectRow(row)
                    self.profile_table_widget.setCurrentCell(row, 0)
                    self.profile_table_widget.setFocus()
                    break
        except Exception as e:
            logger.debug(f"Error reselecting profile: {e}")
    
    def delete_selected_profile(self):
        """Delete the selected profile."""
        try:
            profile = self.get_selected_profile()
            if not profile:
                self.show_themed_warning("경고", "삭제할 프로필을 선택해주세요.")
                return
                
            # Confirm deletion with explicit theme colors for readable text.
            confirmation = QMessageBox(self)
            confirmation.setIcon(QMessageBox.Question)
            confirmation.setWindowTitle("프로필 삭제")
            confirmation.setText(
                f"프로필 '{profile.name}'을 삭제하시겠습니까?\n\n"
                "이 작업은 되돌릴 수 없습니다."
            )
            confirmation.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            confirmation.setDefaultButton(QMessageBox.No)
            confirmation.setStyleSheet(self.theme_manager.get_message_box_style())
            reply = confirmation.exec_()
            
            if reply == QMessageBox.Yes:
                success = self.profile_manager.delete_profile(profile.id)
                if not success:
                    self.show_themed_warning(
                        "프로필 삭제",
                        f"프로필 '{profile.name}'을 삭제하지 못했습니다. 다시 시도해주세요."
                    )
                    return

                # Refresh profile table and list
                if hasattr(self, 'profile_table_widget'):
                    self.refresh_profile_table()
                self.refresh_profile_list()
                self.status_label.setText(f"프로필 '{profile.name}'이 삭제되었습니다")
                
        except Exception as e:
            logger.error(f"Error deleting profile: {e}")
            self.show_themed_critical("오류", f"프로필 삭제 중 오류가 발생했습니다:\n{str(e)}")
    
    def apply_selected_profile(self):
        """Apply the selected profile to all matching windows based on stored pattern."""
        try:
            profile = self.get_selected_profile()
            if not profile:
                self.show_themed_warning("경고", "적용할 프로필을 선택해주세요.")
                return
            
            logger.info(f"Applying profile '{profile.name}' to matching windows")
            
            # Refresh window list to get current windows
            self.refresh_window_list()
            
            # Get all current windows for pattern matching
            windows_info = []
            for window in self.window_list:
                # Validate window handle before processing
                try:
                    import win32gui
                    if not win32gui.IsWindow(window.hwnd):
                        logger.warning(f"Skipping invalid window handle: {window.hwnd} ({window.title})")
                        continue
                except Exception as e:
                    logger.warning(f"Cannot validate window handle {window.hwnd}: {e}")
                    continue
                    
                window_info = {
                    'hwnd': window.hwnd,
                    'title': window.title,
                    'process_name': window.process_name,
                    'executable_path': window.executable_path,
                    'rect': window.rect,
                    'is_maximized': window.is_maximized,
                    'is_minimized': window.is_minimized,
                    'is_visible': window.is_visible
                }
                windows_info.append(window_info)
            
            # Find windows that match this profile's pattern
            matching_windows = []
            for window_info in windows_info:
                if profile.matches_window(window_info):
                    matching_windows.append(window_info)
            
            if not matching_windows:
                message = f"프로필 '{profile.name}'과 일치하는 창을 찾지 못했습니다"
                self.status_label.setText(message)
                logger.info(message)
                return
            
            # Apply profile to all matching windows
            applied_count = 0
            failed_count = 0
            
            for window_info in matching_windows:
                try:
                    success = self.profile_manager.apply_profile(profile.id, window_info)
                    if success:
                        applied_count += 1
                        logger.info(f"Successfully applied profile to window: {window_info['title']}")
                    else:
                        failed_count += 1
                        logger.warning(f"Failed to apply profile to window: {window_info['title']}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error applying profile to window {window_info['title']}: {e}")
            
            # Show results to user
            if applied_count > 0:
                message = f"프로필 '{profile.name}'이 {applied_count}개 창에 적용되었습니다."
                if failed_count > 0:
                    message += f"\n({failed_count}개 창 적용 실패)"
                self.status_label.setText(message)
                # 알림창 대신 콘솔 로그와 소리 알림 사용
                logger.info(f"프로필 적용 완료: {message}")
                # 소리 알림 비활성화 (사용자 요청)
                # try:
                #     import winsound
                #     winsound.Beep(800, 200)  # 성공 알림음
                # except:
                #     pass
            else:
                logger.warning(f"프로필 적용 실패: 프로필 '{profile.name}' 적용에 실패했습니다.")
                # 소리 알림 비활성화 (사용자 요청)
                # try:
                #     import winsound
                #     winsound.Beep(400, 300)  # 실패 알림음
                # except:
                #     pass
                
        except Exception as e:
            logger.error(f"Error applying profile: {e}")
            import traceback
            traceback.print_exc()
            self.show_themed_critical("오류", f"프로필 적용 중 오류가 발생했습니다:\n{str(e)}")
    
    def load_selected_profile(self):
        """Load the selected profile into the coordinate controls."""
        try:
            if not hasattr(self, 'profile_combo'):
                return  # Profile combo not available in current layout
                
            profile_name = self.profile_combo.currentText()
            
            if profile_name == "새 프로필...":
                # Create new profile dialog
                self.save_current_as_profile()
                return
            
            # Get profile by name
            profile = None
            profiles = self.profile_manager.list_profiles()
            for p in profiles:
                if p.name == profile_name:
                    profile = p
                    break
            
            if not profile:
                self.show_themed_warning("경고", f"프로필 '{profile_name}'을 찾을 수 없습니다.")
                return
            
            # Load profile configuration into coordinate controls if they exist
            if profile.window_config:
                if hasattr(self, 'x_spinbox'):
                    self.x_spinbox.setValue(profile.window_config.x)
                if hasattr(self, 'y_spinbox'):
                    self.y_spinbox.setValue(profile.window_config.y)
                if hasattr(self, 'width_spinbox'):
                    self.width_spinbox.setValue(profile.window_config.width)
                if hasattr(self, 'height_spinbox'):
                    self.height_spinbox.setValue(profile.window_config.height)
                
                self.status_label.setText(f"프로필 '{profile_name}'을 불러왔습니다")
            else:
                QMessageBox.warning(self, "경고", f"프로필 '{profile_name}'에 저장된 설정이 없습니다.")
                
        except Exception as e:
            logger.error(f"Error loading profile: {e}")
            QMessageBox.critical(self, "오류", f"프로필 불러오기 중 오류가 발생했습니다:\n{str(e)}")
    
    def save_current_as_profile(self):
        """Open a prefilled editor for a profile based on the selected window."""
        try:
            if not self.current_window:
                self.show_themed_warning("경고", "프로필을 저장하려면 먼저 창을 선택해주세요.")
                return
            window_info = {
                'hwnd': self.current_window.hwnd,
                'title': self.current_window.title,
                'process_name': self.current_window.process_name,
                'pid': self.current_window.pid,
                'executable_path': self.current_window.executable_path,
                'rect': self.current_profile_rect(),
            }

            dialog = ProfileEditorDialog(
                parent=self,
                window_info=window_info,
                save_handler=self.on_profile_created,
            )
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            self.show_themed_critical("오류", f"프로필 저장 중 오류가 발생했습니다:\n{str(e)}")

    def current_profile_rect(self):
        """Return the coordinates currently shown in the main window controls."""
        if all(hasattr(self, name) for name in (
            'x_spinbox', 'y_spinbox', 'width_spinbox', 'height_spinbox'
        )):
            x = self.x_spinbox.value()
            y = self.y_spinbox.value()
            width = self.width_spinbox.value()
            height = self.height_spinbox.value()
            return WindowRect(x, y, x + width, y + height)
        return self.current_window.rect

    def on_profile_created(self, profile_data: dict):
        """Persist the profile data emitted by a new profile editor dialog."""
        try:
            from core.profile_manager import MatchingCriteria, MatchingStrategy, WindowConfiguration

            matching_data = profile_data['matching_criteria']
            criteria = MatchingCriteria(
                strategy=MatchingStrategy(matching_data['strategy']),
                window_title_pattern=matching_data.get('window_title_pattern'),
                process_name_pattern=matching_data.get('process_name_pattern'),
                executable_path_pattern=matching_data.get('executable_path_pattern'),
                case_sensitive=matching_data.get('case_sensitive', False),
                priority=matching_data.get('priority', 50),
            )
            profile = self.profile_manager.create_profile(
                name=profile_data['name'],
                description=profile_data.get('description', ''),
                matching_criteria=criteria,
                auto_apply=profile_data.get('auto_apply', False),
                enabled=profile_data.get('enabled', True),
                window_config=WindowConfiguration(**profile_data['window_config']),
            )

            for field_name in (
                'hotkey_enabled', 'hotkey_combination', 'hotkey_action', 'lock_position',
                'mouse_constraint', 'constraint_mode', 'constraint_escape_key', 'auto_restore',
            ):
                if field_name in profile_data:
                    setattr(profile, field_name, profile_data[field_name])
            self.profile_manager.save_profiles()

            self.refresh_profile_list()
            if hasattr(self, 'profile_table_widget'):
                self.refresh_profile_table()
                self._reselect_profile(profile.id)
            self.status_label.setText(f"프로필 '{profile.name}'을 저장했습니다")
            return profile
        except Exception as e:
            logger.error(f"Error creating profile from editor data: {e}")
            self.show_themed_critical("오류", f"프로필 저장 중 오류가 발생했습니다:\n{str(e)}")
            return None
    
    def update_selected_profile(self):
        """Update the selected profile with current settings."""
        try:
            if not hasattr(self, 'profile_combo'):
                return  # Profile combo not available in current layout
                
            profile_name = self.profile_combo.currentText()
            
            if profile_name == "새 프로필...":
                QMessageBox.warning(self, "경고", "업데이트할 프로필을 선택해주세요.")
                return
            
            if not self.current_window:
                QMessageBox.warning(self, "경고", "프로필을 업데이트하려면 먼저 창을 선택해주세요.")
                return
            
            # Get profile by name
            profile = None
            profiles = self.profile_manager.list_profiles()
            for p in profiles:
                if p.name == profile_name:
                    profile = p
                    break
            
            if not profile:
                self.show_themed_warning("경고", f"프로필 '{profile_name}'을 찾을 수 없습니다.")
                return
            
            # Update window configuration
            from core.profile_manager import WindowConfiguration
            
            # Get coordinates from spinboxes if they exist, otherwise use current window
            if hasattr(self, 'x_spinbox') and hasattr(self, 'y_spinbox') and hasattr(self, 'width_spinbox') and hasattr(self, 'height_spinbox'):
                x = self.x_spinbox.value()
                y = self.y_spinbox.value()
                width = self.width_spinbox.value()
                height = self.height_spinbox.value()
            else:
                rect = self.current_window.rect
                x, y, width, height = rect.left, rect.top, rect.width, rect.height
            
            profile.window_config = WindowConfiguration(
                x=x,
                y=y,
                width=width,
                height=height,
                is_maximized=False,
                is_minimized=False
            )
            
            # Update profile metadata
            import time
            profile.modified_at = time.time()
            
            # Save profiles
            self.profile_manager.save_profiles()
            
            self.status_label.setText(f"프로필 '{profile.name}'을 업데이트했습니다")
            self.show_themed_information("성공", f"프로필 '{profile.name}'을 성공적으로 업데이트했습니다.")
            
        except Exception as e:
            logger.error(f"Error updating profile: {e}")
            self.show_themed_critical("오류", f"프로필 업데이트 중 오류가 발생했습니다:\n{str(e)}")
    
    def add_selected_window_to_profile(self):
        """Add the selected window to a new profile."""
        if not self.current_window:
            self.show_themed_warning("경고", "프로필에 추가할 창을 먼저 선택해주세요.")
            return
        
        # Use the save_current_as_profile method which already handles this functionality
        self.save_current_as_profile()
    
    # Phase 2: Auto-apply system methods
    def toggle_auto_apply(self, enabled: bool):
        """Toggle automatic profile application system."""
        try:
            if enabled:
                # Update configuration
                self.update_monitoring_config()
                
                # Start monitoring
                success = self.window_monitor.start()
                if success:
                    self.auto_apply_status_label.setText("활성화됨")
                    self.auto_apply_status_label.setStyleSheet("font-weight: bold;")
                    self.force_scan_button.setEnabled(True)
                    self.status_label.setText("자동 프로필 적용이 시작되었습니다")
                    
                    # Start statistics update timer
                    if not hasattr(self, 'stats_timer'):
                        self.stats_timer = QTimer()
                        self.stats_timer.timeout.connect(self.update_auto_apply_stats)
                    self.stats_timer.start(5000)  # Update every 5 seconds
                    
                    logger.info("Auto-apply system started")
                else:
                    self.auto_apply_master_checkbox.setChecked(False)
                    QMessageBox.warning(self, "시작 실패", "자동 프로필 적용 시스템을 시작할 수 없습니다.")
            else:
                # Stop monitoring
                success = self.window_monitor.stop()
                if success:
                    self.auto_apply_status_label.setText("비활성화됨")
                    self.auto_apply_status_label.setStyleSheet("font-weight: bold;")
                    self.force_scan_button.setEnabled(False)
                    self.status_label.setText("자동 프로필 적용이 중지되었습니다")
                    
                    # Stop statistics timer
                    if hasattr(self, 'stats_timer'):
                        self.stats_timer.stop()
                    
                    logger.info("Auto-apply system stopped")
                
        except Exception as e:
            logger.error(f"Error toggling auto-apply: {e}")
            QMessageBox.critical(self, "오류", f"자동 적용 시스템 제어 중 오류 발생:\n{str(e)}")
    
    def update_monitoring_config(self):
        """Update monitoring configuration from UI settings."""
        try:
            if hasattr(self, 'monitoring_interval_spinbox'):
                self.monitor_config.polling_interval = self.monitoring_interval_spinbox.value()
            if hasattr(self, 'startup_delay_spinbox'):
                self.monitor_config.startup_delay = self.startup_delay_spinbox.value()
            
            # Update the monitor if it's running
            if hasattr(self.window_monitor, '_running') and self.window_monitor._running:
                # The monitor will pick up the new config on next cycle
                logger.debug(f"Updated monitoring config: interval={self.monitor_config.polling_interval}s, delay={self.monitor_config.startup_delay}s")
                
        except Exception as e:
            logger.error(f"Error updating monitoring config: {e}")
    
    def force_scan_windows(self):
        """Force an immediate scan for windows to apply profiles."""
        try:
            if hasattr(self.window_monitor, '_running') and self.window_monitor._running:
                self.window_monitor.force_scan()
                self.status_label.setText("수동 검색 실행됨")
                
                # Update stats immediately
                QTimer.singleShot(1000, self.update_auto_apply_stats)
            else:
                QMessageBox.information(self, "알림", "자동 프로필 적용이 비활성화되어 있습니다.")
                
        except Exception as e:
            logger.error(f"Error in force scan: {e}")
            QMessageBox.critical(self, "오류", f"수동 검색 중 오류 발생:\n{str(e)}")
    
    def update_auto_apply_stats(self):
        """Update the auto-apply statistics display."""
        try:
            if hasattr(self, 'window_monitor'):
                stats = self.window_monitor.get_statistics()
                
                stats_text = f"감지: {stats.get('windows_detected', 0)}개 | 적용: {stats.get('profiles_applied', 0)}개 | 실패: {stats.get('apply_failures', 0)}개"
                
                if hasattr(self, 'stats_label'):
                    self.stats_label.setText(stats_text)
                
                # Update status if there's recent activity
                if stats.get('last_activity'):
                    import time
                    if time.time() - stats['last_activity'] < 10:  # Recent activity within 10 seconds
                        if hasattr(self, 'auto_apply_status_label'):
                            self.auto_apply_status_label.setText("활성화됨 (활동 중)")
                    else:
                        if hasattr(self, 'auto_apply_status_label') and self.auto_apply_status_label.text() == "활성화됨 (활동 중)":
                            self.auto_apply_status_label.setText("활성화됨")
                
        except Exception as e:
            logger.error(f"Error updating auto-apply stats: {e}")
    
    def on_profile_auto_applied(self, hwnd: int, profile):
        """Callback when a profile is automatically applied."""
        try:
            # Get window info for display
            windows = self.enumerator.enumerate_windows()
            window = next((w for w in windows if w.hwnd == hwnd), None)
            
            window_name = window.title if window else f"Window {hwnd}"
            
            self.status_label.setText(f"프로필 '{profile.name}'이 '{window_name}'에 자동 적용됨")
            
            # Refresh window list to show updated coordinates
            QTimer.singleShot(1000, self.refresh_window_list)
            
            logger.info(f"Auto-applied profile '{profile.name}' to window '{window_name}'")
            
        except Exception as e:
            logger.error(f"Error in profile auto-applied callback: {e}")
    
    def _queue_profile_auto_applied(self, hwnd: int, profile):
        """Move monitor-thread notifications onto the Qt UI thread."""
        self.auto_profile_applied_signal.emit(hwnd, profile)

    def _queue_monitor_error(self, error_type: str, exception: Exception):
        """Move monitor-thread errors onto the Qt UI thread."""
        self.monitor_error_signal.emit(error_type, exception)

    def toggle_auto_apply_monitor(self):
        """Start or stop monitoring for profiles that explicitly enable auto apply."""
        try:
            is_running = self.window_monitor.get_statistics().get('is_running', False)
            if is_running:
                self.window_monitor.stop()
                self.auto_apply_monitor_button.setText("자동 감지 켜기")
                self.auto_apply_monitor_status_label.setText("자동 감지 꺼짐")
                self.status_label.setText("새 창 자동 감지를 중지했습니다")
                return

            enabled_profiles = [
                profile for profile in self.profile_manager.list_profiles()
                if profile.enabled and profile.auto_apply
            ]
            if not enabled_profiles:
                self.show_themed_warning(
                    "자동 감지",
                    "자동 적용을 켠 활성 프로필이 없습니다. 프로필 편집에서 먼저 선택해주세요.",
                )
                return

            if self.window_monitor.start():
                self.auto_apply_monitor_button.setText("자동 감지 끄기")
                self.auto_apply_monitor_status_label.setText(
                    f"자동 감지 중: {len(enabled_profiles)}개 프로필"
                )
                self.status_label.setText("새 창 자동 감지를 시작했습니다")
            else:
                self.show_themed_warning("자동 감지", "자동 감지를 시작하지 못했습니다.")
        except Exception as e:
            logger.error(f"Error toggling automatic profile monitor: {e}")
            self.show_themed_critical("자동 감지 오류", str(e))

    def show_selected_profile_preview(self):
        """Display a temporary overlay at the selected profile's saved geometry."""
        profile = self.get_selected_profile()
        if not profile:
            self.show_themed_warning("프로필 미리보기", "미리볼 프로필을 선택해주세요.")
            return
        if not profile.window_config or not profile.window_config.validate():
            self.show_themed_warning("프로필 미리보기", "유효한 위치와 크기가 저장된 프로필이 아닙니다.")
            return

        self._close_profile_preview()
        overlay = ProfilePreviewOverlay(profile, self.theme_manager)
        self.profile_preview_overlay = overlay
        overlay.show()
        self.status_label.setText("프로필 위치 미리보기 표시 중: 3초")
        QTimer.singleShot(3000, lambda: self._close_profile_preview(overlay))

    def _close_profile_preview(self, overlay=None):
        """Close the current preview overlay when it is still the active one."""
        current_overlay = self.profile_preview_overlay
        if not current_overlay or (overlay is not None and overlay is not current_overlay):
            return
        current_overlay.close()
        current_overlay.deleteLater()
        self.profile_preview_overlay = None

    def on_monitor_error(self, error_type: str, exception: Exception):
        """Callback for monitoring system errors."""
        try:
            logger.error(f"Monitor error ({error_type}): {exception}")
            
            # Show error in status
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"모니터링 오류: {error_type}")
            
            # For critical errors, show message box
            if "critical" in error_type.lower():
                QMessageBox.warning(
                    self, "모니터링 오류", 
                    f"자동 적용 시스템에서 오류가 발생했습니다:\n{error_type}\n\n"
                    f"자동 적용을 다시 시작해보세요."
                )
                
        except Exception as e:
            logger.error(f"Error in monitor error callback: {e}")
    
    def create_profile_panel_direct(self):
        """Create profile list panel directly without wrapper widget."""
        # Create profile group with no padding
        profile_group = QGroupBox("프로필 목록")
        profile_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        profile_group.setStyleSheet("QGroupBox { padding: 0px; margin: 0px; }")  # Force zero padding
        # Removed maximum height to allow expansion with stretch factor
        profile_layout = QVBoxLayout(profile_group)
        profile_layout.setContentsMargins(0, 0, 0, 0)  # Remove all margins
        profile_layout.setSpacing(0)  # Remove spacing between items
        
        # Create profile table
        self.profile_table_widget = QTableWidget()
        self.profile_table_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Removed all height constraints to allow complete flexibility
        # Table should expand to fill ALL available space in the profile group
        self.profile_table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.profile_table_widget.setSelectionMode(QTableWidget.SingleSelection)
        self.profile_table_widget.setAlternatingRowColors(True)
        self.profile_table_widget.setEditTriggers(QTableWidget.NoEditTriggers)  # 편집 불가
        
        # Set up profile table headers - Add shortcut and mouse constraint columns
        profile_headers = ["프로필명", "대상창/프로세스", "단축키", "마우스 가둠", "X", "Y", "폭", "높이", "자동적용"]
        self.profile_table_widget.setColumnCount(len(profile_headers))
        self.profile_table_widget.setHorizontalHeaderLabels(profile_headers)
        
        # Configure profile table column widths with responsive design
        profile_header = self.profile_table_widget.horizontalHeader()
        profile_header.setDefaultSectionSize(80)
        
        # Set column widths - coordinate columns same as window list (80px)
        self.profile_table_widget.setColumnWidth(0, 150)  # 프로필명 - will be resizable
        self.profile_table_widget.setColumnWidth(1, 200)  # 대상창/프로세스 - will be resizable
        self.profile_table_widget.setColumnWidth(2, 120)  # 단축키 - fixed
        self.profile_table_widget.setColumnWidth(3, 110)  # 마우스 가둠 - fixed (10px 증가)
        self.profile_table_widget.setColumnWidth(4, 80)   # X - fixed (same as window list)
        self.profile_table_widget.setColumnWidth(5, 80)   # Y - fixed (same as window list)
        self.profile_table_widget.setColumnWidth(6, 80)   # 폭 - fixed (same as window list)
        self.profile_table_widget.setColumnWidth(7, 80)   # 높이 - fixed (same as window list)
        self.profile_table_widget.setColumnWidth(8, 104)  # 자동적용 - fixed (80 * 1.3 = 104, 30% wider)
        
        # Set resize modes - only profile name and target columns can expand
        profile_header.setSectionResizeMode(0, profile_header.Stretch)    # 프로필명 - expandable
        profile_header.setSectionResizeMode(1, profile_header.Stretch)    # 대상창/프로세스 - expandable
        profile_header.setSectionResizeMode(2, profile_header.Fixed)      # 단축키 - fixed
        profile_header.setSectionResizeMode(3, profile_header.Fixed)      # 마우스 가둠 - fixed
        profile_header.setSectionResizeMode(4, profile_header.Fixed)      # X - fixed
        profile_header.setSectionResizeMode(5, profile_header.Fixed)      # Y - fixed
        profile_header.setSectionResizeMode(6, profile_header.Fixed)      # 폭 - fixed
        profile_header.setSectionResizeMode(7, profile_header.Fixed)      # 높이 - fixed
        profile_header.setSectionResizeMode(8, profile_header.Fixed)      # 자동적용 - fixed
        
        # Enable sorting for profile table
        self.profile_table_widget.setSortingEnabled(True)
        
        # Connect selection change event
        self.profile_table_widget.selectionModel().selectionChanged.connect(self.on_profile_selected)
        
        # Connect double-click event to open profile editor
        self.profile_table_widget.itemDoubleClicked.connect(self.on_profile_double_clicked)
        
        profile_layout.addWidget(self.profile_table_widget)
        
        # Give maximum stretch to the table widget - it should take ALL available space
        profile_layout.setStretch(profile_layout.count() - 1, 10)
        
        # Create profile management buttons with zero margins
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)  # No margins at all
        button_layout.setSpacing(2)  # Minimal spacing between buttons
        
        self.edit_profile_button = QPushButton("편집")
        self.edit_profile_button.setToolTip("선택된 프로필을 편집합니다")
        self.edit_profile_button.setEnabled(False)
        button_layout.addWidget(self.edit_profile_button)
        
        self.delete_profile_button = QPushButton("삭제")
        self.delete_profile_button.setToolTip("선택된 프로필을 삭제합니다")
        self.delete_profile_button.setEnabled(False)
        button_layout.addWidget(self.delete_profile_button)
        
        self.apply_profile_button = QPushButton("적용")
        self.apply_profile_button.setToolTip("선택된 프로필을 현재 창에 적용합니다")
        self.apply_profile_button.setEnabled(False)
        button_layout.addWidget(self.apply_profile_button)
        
        self.apply_all_profiles_button = QPushButton("전체 적용")
        self.apply_all_profiles_button.setToolTip("모든 자동적용 프로필을 해당 창에 적용합니다")
        button_layout.addWidget(self.apply_all_profiles_button)
        
        self.profile_count_label = QLabel("프로필 0개")
        button_layout.addWidget(self.profile_count_label)
        
        # Add button layout with explicit space reservation
        profile_layout.addLayout(button_layout)
        
        # Give most space to table, minimal to buttons
        profile_layout.setStretch(0, 1)   # Table gets all stretch space
        profile_layout.setStretch(1, 0)   # Button layout gets only what it needs
        
        # Set minimal button heights to save space
        for button in [self.edit_profile_button, self.delete_profile_button, 
                      self.apply_profile_button, self.apply_all_profiles_button]:
            button.setMinimumHeight(24)  # Smaller buttons
            button.setMaximumHeight(28)  # Prevent buttons from growing too much
        
        # Load initial profile data
        self.refresh_profile_table()
        
        return profile_group

    def create_profile_panel_redesigned(self):
        """Create redesigned profile panel with zero empty space guarantee."""
        # Use QFrame instead of QGroupBox for tighter control - remove borders
        profile_container = QFrame()
        profile_container.setFrameStyle(QFrame.NoFrame)  # Remove frame border
        profile_container.setLineWidth(0)  # No border line
        profile_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Create extremely tight layout
        profile_layout = QVBoxLayout(profile_container)
        profile_layout.setContentsMargins(0, 0, 0, 0)  # No margins at all
        profile_layout.setSpacing(1)  # Minimal spacing
        
        # Add title label instead of QGroupBox
        title_label = QLabel("프로필 목록")
        title_label.setStyleSheet("font-weight: bold; padding: 2px;")
        title_label.setMaximumHeight(20)  # Fixed small height
        profile_layout.addWidget(title_label)
        
        # Create profile table with aggressive space utilization
        self.profile_table_widget = QTableWidget()
        self.profile_table_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.profile_table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.profile_table_widget.setSelectionMode(QTableWidget.SingleSelection)
        self.profile_table_widget.setAlternatingRowColors(True)
        self.profile_table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Set up headers - same as original
        profile_headers = ["프로필명", "대상창/프로세스", "단축키", "마우스 가둠", "X", "Y", "폭", "높이", "자동적용"]
        self.profile_table_widget.setColumnCount(len(profile_headers))
        self.profile_table_widget.setHorizontalHeaderLabels(profile_headers)
        
        # Configure column widths - same as original
        profile_header = self.profile_table_widget.horizontalHeader()
        profile_header.setDefaultSectionSize(80)
        self.profile_table_widget.setColumnWidth(0, 150)
        self.profile_table_widget.setColumnWidth(1, 200)
        self.profile_table_widget.setColumnWidth(2, 120)
        self.profile_table_widget.setColumnWidth(3, 110)
        self.profile_table_widget.setColumnWidth(4, 80)
        self.profile_table_widget.setColumnWidth(5, 80)
        self.profile_table_widget.setColumnWidth(6, 80)
        self.profile_table_widget.setColumnWidth(7, 80)
        self.profile_table_widget.setColumnWidth(8, 104)
        
        # Set resize modes - same as original
        profile_header.setSectionResizeMode(0, profile_header.Stretch)
        profile_header.setSectionResizeMode(1, profile_header.Stretch)
        for i in range(2, 9):
            profile_header.setSectionResizeMode(i, profile_header.Fixed)
        
        self.profile_table_widget.setSortingEnabled(True)
        self.profile_table_widget.selectionModel().selectionChanged.connect(self.on_profile_selected)
        self.profile_table_widget.itemDoubleClicked.connect(self.on_profile_double_clicked)
        
        # Add table with maximum stretch - this should consume ALL available space
        profile_layout.addWidget(self.profile_table_widget, 1)  # stretch=1
        
        # Keep enough room for the theme button padding and text baseline.
        profile_button_height = 34
        profile_button_bar_height = 46
        button_widget = QFrame()
        button_widget.setFixedHeight(profile_button_bar_height)
        self.profile_button_bar = button_widget
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(4, 6, 4, 6)
        button_layout.setSpacing(4)
        
        # Create buttons with fixed size
        self.edit_profile_button = QPushButton("편집")
        self.edit_profile_button.setToolTip("선택된 프로필을 편집합니다")
        self.edit_profile_button.setEnabled(False)
        self.edit_profile_button.setFixedHeight(profile_button_height)
        
        self.delete_profile_button = QPushButton("삭제")
        self.delete_profile_button.setToolTip("선택된 프로필을 삭제합니다")
        self.delete_profile_button.setEnabled(False)
        self.delete_profile_button.setFixedHeight(profile_button_height)
        
        self.apply_profile_button = QPushButton("적용")
        self.apply_profile_button.setToolTip("선택된 프로필을 현재 창에 적용합니다")
        self.apply_profile_button.setEnabled(False)
        self.apply_profile_button.setFixedHeight(profile_button_height)
        
        self.apply_all_profiles_button = QPushButton("전체 적용")
        self.apply_all_profiles_button.setToolTip("모든 자동적용 프로필을 해당 창에 적용합니다")
        self.apply_all_profiles_button.setFixedHeight(profile_button_height)

        self.profile_preview_button = QPushButton("미리보기")
        self.profile_preview_button.setToolTip("저장된 위치와 크기를 3초 동안 표시합니다")
        self.profile_preview_button.setEnabled(False)
        self.profile_preview_button.setFixedHeight(profile_button_height)
        self.profile_preview_button.clicked.connect(self.show_selected_profile_preview)

        self.auto_apply_monitor_button = QPushButton("자동 감지 켜기")
        self.auto_apply_monitor_button.setToolTip("자동 적용 프로필과 일치하는 새 창을 감지합니다")
        self.auto_apply_monitor_button.setFixedHeight(profile_button_height)
        self.auto_apply_monitor_button.clicked.connect(self.toggle_auto_apply_monitor)

        self.auto_apply_monitor_status_label = QLabel("자동 감지 꺼짐")
        self.auto_apply_monitor_status_label.setFixedHeight(profile_button_height)
        self.auto_apply_monitor_status_label.setAlignment(Qt.AlignVCenter)
        
        self.profile_count_label = QLabel("프로필 0개")
        self.profile_count_label.setFixedHeight(profile_button_height)
        self.profile_count_label.setAlignment(Qt.AlignVCenter)
        
        # Add buttons to layout
        for widget in [self.edit_profile_button, self.delete_profile_button,
                       self.apply_profile_button, self.apply_all_profiles_button,
                       self.profile_preview_button, self.auto_apply_monitor_button,
                       self.auto_apply_monitor_status_label, self.profile_count_label]:
            button_layout.addWidget(widget)
        
        # Add button bar with NO stretch (stretch=0)
        profile_layout.addWidget(button_widget, 0)  # stretch=0 - fixed size only
        
        # Load profile data
        self.refresh_profile_table()
        
        return profile_container

    
    def refresh_profile_table(self):
        """Refresh the profile table with current profiles."""
        try:
            # Temporarily disable sorting
            self.profile_table_widget.setSortingEnabled(False)
            
            # Clear existing rows
            self.profile_table_widget.setRowCount(0)
            
            # Get profiles from profile manager
            profiles = self.profile_manager.list_profiles()
            
            # Set row count
            self.profile_table_widget.setRowCount(len(profiles))
            
            for row, profile in enumerate(profiles):
                # Column 0: Profile Name
                name_item = QTableWidgetItem(profile.name)
                name_item.setData(Qt.UserRole, profile.id)  # Store profile ID
                
                # Column 1: Target Window/Process
                target_text = "모든 창"
                if hasattr(profile, 'matching_criteria') and profile.matching_criteria:
                    if profile.matching_criteria.window_title_pattern:
                        target_text = profile.matching_criteria.window_title_pattern
                    elif profile.matching_criteria.process_name_pattern:
                        target_text = profile.matching_criteria.process_name_pattern
                    elif profile.matching_criteria.executable_path_pattern:
                        target_text = (
                            "경로: " + os.path.basename(
                                profile.matching_criteria.executable_path_pattern
                            )
                        )
                
                target_item = QTableWidgetItem(target_text)
                if (
                    hasattr(profile, 'matching_criteria')
                    and profile.matching_criteria
                    and profile.matching_criteria.executable_path_pattern
                ):
                    target_item.setToolTip(profile.matching_criteria.executable_path_pattern)
                
                # Column 2: Shortcut Key - Get hotkey configuration
                shortcut_text = "-"
                if hasattr(profile, 'hotkey_enabled') and profile.hotkey_enabled:
                    if hasattr(profile, 'hotkey_combination') and profile.hotkey_combination:
                        shortcut_text = profile.hotkey_combination
                
                shortcut_item = QTableWidgetItem(shortcut_text)
                
                # Column 3: Mouse Constraint - Get cursor control configuration
                mouse_constraint_text = "아니오"
                if hasattr(profile, 'mouse_constraint') and profile.mouse_constraint:
                    mouse_constraint_text = "예"
                
                mouse_constraint_item = QTableWidgetItem(mouse_constraint_text)
                
                # Column 4-7: Coordinates (X, Y, Width, Height)
                if hasattr(profile, 'window_config') and profile.window_config:
                    x_item = QTableWidgetItem(str(profile.window_config.x))
                    y_item = QTableWidgetItem(str(profile.window_config.y))
                    width_item = QTableWidgetItem(str(profile.window_config.width))
                    height_item = QTableWidgetItem(str(profile.window_config.height))
                    
                    # Set numeric data for proper sorting
                    x_item.setData(Qt.UserRole + 1, profile.window_config.x)
                    y_item.setData(Qt.UserRole + 1, profile.window_config.y)
                    width_item.setData(Qt.UserRole + 1, profile.window_config.width)
                    height_item.setData(Qt.UserRole + 1, profile.window_config.height)
                else:
                    x_item = QTableWidgetItem("-")
                    y_item = QTableWidgetItem("-")
                    width_item = QTableWidgetItem("-")
                    height_item = QTableWidgetItem("-")
                
                # Column 8: Auto Apply
                auto_apply_text = "예" if hasattr(profile, 'auto_apply') and profile.auto_apply else "아니오"
                auto_apply_item = QTableWidgetItem(auto_apply_text)
                
                # Set row color for auto-apply profiles
                if hasattr(profile, 'auto_apply') and profile.auto_apply:
                    color = QColor("#28a745")  # Green for auto-apply
                    name_item.setForeground(color)
                
                # Add items to table
                self.profile_table_widget.setItem(row, 0, name_item)
                self.profile_table_widget.setItem(row, 1, target_item)
                self.profile_table_widget.setItem(row, 2, shortcut_item)
                self.profile_table_widget.setItem(row, 3, mouse_constraint_item)
                self.profile_table_widget.setItem(row, 4, x_item)
                self.profile_table_widget.setItem(row, 5, y_item)
                self.profile_table_widget.setItem(row, 6, width_item)
                self.profile_table_widget.setItem(row, 7, height_item)
                self.profile_table_widget.setItem(row, 8, auto_apply_item)
            
            # Re-enable sorting
            self.profile_table_widget.setSortingEnabled(True)
            
            # Update count
            self.profile_count_label.setText(f"프로필 {len(profiles)}개")
            
        except Exception as e:
            logger.error(f"Error refreshing profile table: {e}")
            self.profile_count_label.setText("프로필 0개 (오류)")
    
    def setup_system_tray(self):
        """Create the system tray controls when the operating system supports them."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray is not available; close will exit the application")
            return

        tray_icon = self.windowIcon()
        if tray_icon.isNull():
            tray_icon = QApplication.style().standardIcon(QStyle.SP_ComputerIcon)

        self.tray_icon = QSystemTrayIcon(tray_icon, self)
        self.tray_icon.setToolTip("WindowResizer")
        self.tray_menu = QMenu(self)
        self.tray_menu.addAction("창 열기", self.restore_from_tray)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction("프로그램 종료", self.quit_application)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def restore_from_tray(self):
        """Restore the main window after it was hidden in the system tray."""
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def on_tray_icon_activated(self, reason):
        """Restore the application from a primary or double tray click."""
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.restore_from_tray()

    def quit_application(self):
        """Run the normal cleanup path and exit the application explicitly."""
        self._quit_requested = True
        self.close()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def closeEvent(self, event):
        """Hide in the system tray unless the user explicitly exits the app."""
        if (
            not self._quit_requested
            and self.tray_icon is not None
            and self.tray_icon.isVisible()
        ):
            event.ignore()
            self.hide()
            if not self._tray_notification_shown:
                self.tray_icon.showMessage(
                    "WindowResizer",
                    "창을 닫아도 시스템 트레이에서 계속 실행됩니다.",
                    QSystemTrayIcon.Information,
                    3000,
                )
                self._tray_notification_shown = True
            return

        # Stop timers
        self.auto_refresh_timer.stop()
        self.coordinate_timer.stop()
        
        # Stop update thread
        if self.update_thread and self.update_thread.isRunning():
            self.update_thread.quit()
            self.update_thread.wait()

        if hasattr(self, 'window_monitor'):
            self.window_monitor.stop()
        self._close_profile_preview()
        if self.tray_icon is not None:
            self.tray_icon.hide()
        
        event.accept()
    
    def perform_search(self):
        """Perform search based on search input."""
        if not hasattr(self, 'search_input'):
            return
            
        search_text = self.search_input.text().strip().lower()
        if not search_text:
            # Clear search - show all windows
            self.refresh_window_list()
            return
        
        # Filter window list based on search text
        filtered_windows = []
        for window in self.window_list:
            if (search_text in window.title.lower() or 
                search_text in window.process_name.lower()):
                filtered_windows.append(window)
        
        # Update table with filtered results
        self.update_window_table(filtered_windows)
        self.status_label.setText(f"검색 결과: {len(filtered_windows)}개 창 발견")
    
    def add_selected_to_profile(self):
        """Add selected window to profile."""
        if not self.current_window:
            self.show_themed_warning("경고", "먼저 창을 선택해주세요.")
            return
        
        self.save_current_as_profile()
    
    def update_window_table(self, windows):
        """Update the window table with given windows list."""
        try:
            self.window_list_widget.setRowCount(0)
            self.window_list_widget.setRowCount(len(windows))
            
            for row, window in enumerate(windows):
                # Create table items with window information
                title_item = QTableWidgetItem(window.title)
                title_item.setData(Qt.UserRole, window.hwnd)
                title_item.setToolTip(f"Handle: {window.hwnd}")
                
                pid_item = QTableWidgetItem(str(window.pid))
                process_item = QTableWidgetItem(window.process_name)
                x_item = QTableWidgetItem(str(window.rect.left))
                y_item = QTableWidgetItem(str(window.rect.top))
                width_item = QTableWidgetItem(str(window.rect.width))
                height_item = QTableWidgetItem(str(window.rect.height))
                
                # Set items in table
                self.window_list_widget.setItem(row, 0, title_item)
                self.window_list_widget.setItem(row, 1, pid_item)
                self.window_list_widget.setItem(row, 2, process_item)
                self.window_list_widget.setItem(row, 3, x_item)
                self.window_list_widget.setItem(row, 4, y_item)
                self.window_list_widget.setItem(row, 5, width_item)
                self.window_list_widget.setItem(row, 6, height_item)
            
            # Update count
            self.window_count_label.setText(f"창 {len(windows)}개")
            
        except Exception as e:
            logger.error(f"Error updating window table: {e}")
    
    def update_theme_button_icon(self):
        """Update theme toggle button icon based on current theme."""
        try:
            import os
            from pathlib import Path
            from .theme_manager import ThemeType
            
            # Get current theme type
            current_theme = self.theme_manager.current_theme
            
            # Convert to string if it's an enum
            if hasattr(current_theme, 'value'):
                theme_str = current_theme.value
            else:
                theme_str = str(current_theme).lower()
            
            logger.info(f"Current theme: {theme_str}")
            
            # Set icon path based on current theme (show opposite icon - what it will switch TO)
            if theme_str == "dark":
                # Currently dark mode, show light icon (will switch to light when clicked)
                icon_path = Path(__file__).parent.parent / "img" / "light.png"
                fallback_text = "☀"  # Sun for light mode
            else:
                # Currently light mode, show dark icon (will switch to dark when clicked) 
                icon_path = Path(__file__).parent.parent / "img" / "dark.png"
                fallback_text = "🌙"  # Moon for dark mode
            
            logger.info(f"Looking for icon at: {icon_path}")
            
            if icon_path.exists():
                icon = QIcon(str(icon_path))
                self.theme_toggle_button.setIcon(icon)
                self.theme_toggle_button.setText("")  # Clear text when icon is used
                logger.info(f"Using icon: {icon_path}")
            else:
                # Fallback text if icons not found
                self.theme_toggle_button.setIcon(QIcon())  # Clear icon
                self.theme_toggle_button.setText(fallback_text)
                logger.info(f"Using fallback text: {fallback_text}")
            
        except Exception as e:
            logger.error(f"Error updating theme button icon: {e}")
            # Fallback to text
            self.theme_toggle_button.setText("🎨")
    
    def toggle_theme(self):
        """Toggle between light and dark themes."""
        try:
            from .theme_manager import ThemeType
            
            # Get current theme
            current_theme = self.theme_manager.current_theme
            logger.info(f"Toggle theme - current theme type: {type(current_theme)}, value: {current_theme}")
            
            # Convert to string if it's an enum
            if hasattr(current_theme, 'value'):
                theme_str = current_theme.value
            else:
                theme_str = str(current_theme).lower()
            
            logger.info(f"Toggle theme - theme_str: {theme_str}")
            
            # Toggle theme
            if theme_str == "dark":
                logger.info("Switching to light theme")
                success = self.theme_manager.set_theme(ThemeType.LIGHT, "Light")
                new_theme = "라이트"
            else:
                logger.info("Switching to dark theme")
                success = self.theme_manager.set_theme(ThemeType.DARK, "Dark")
                new_theme = "다크"
            
            logger.info(f"Theme change success: {success}")
            
            # Apply the theme styling immediately
            self.apply_theme_styling()
            
            # Update button icon after a small delay to ensure theme has changed
            QTimer.singleShot(100, self.update_theme_button_icon)
            
            self.status_label.setText(f"테마가 {new_theme} 모드로 변경되었습니다")
            
        except Exception as e:
            logger.error(f"Error toggling theme: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "테마 오류", f"테마 변경 중 오류가 발생했습니다: {str(e)}")
    
    def show_debug_window(self):
        """디버그 창 표시"""
        try:
            if self.debug_window is None:
                from gui.debug_window import DebugWindow
                self.debug_window = DebugWindow(self)
                
            self.debug_window.show()
            self.debug_window.raise_()
            self.debug_window.activateWindow()
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"디버그 창을 열 수 없습니다:\n{str(e)}")

    def apply_resolution_preset(self, width: int, height: int):
        """Apply resolution preset to selected window."""
        current_row = self.window_list_widget.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "경고", "창을 먼저 선택해주세요.")
            return
            
        # Update spinboxes
        self.width_spinbox.setValue(width)
        self.height_spinbox.setValue(height)
        
        # Apply immediately
        self.apply_coordinates()
        
        # Refresh window list
        self.refresh_window_list()
    
    def apply_position_preset(self, position: str):
        """Apply position preset to selected window."""
        current_row = self.window_list_widget.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "경고", "창을 먼저 선택해주세요.")
            return
            
        # Get current window info
        hwnd = int(self.window_list_widget.item(current_row, 1).text())
        
        current_width = self.width_spinbox.value() or 800
        current_height = self.height_spinbox.value() or 600
        try:
            work_area = self.get_work_area_for_window(hwnd)
            x, y = self.calculate_position_in_work_area(
                position, current_width, current_height, work_area, margin=50
            )
        except (KeyError, ValueError) as e:
            logger.error(f"Could not calculate {position} position preset: {e}")
            return
            
        # Update spinboxes
        self.x_spinbox.setValue(x)
        self.y_spinbox.setValue(y)
        
        # Apply immediately
        self.apply_coordinates()
        
        # Refresh window list
        self.refresh_window_list()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("WindowResizer")
    app.setApplicationVersion("0.01.4")
    app.setQuitOnLastWindowClosed(False)
    
    window = WindowResizerMainWindow()
    window.show()
    
    sys.exit(app.exec_())
