"""
System Tray Integration
=======================

Windows system tray integration for background service management.
Provides system tray icon, context menu, and service control interface.

Key Features:
- System tray icon with status indication
- Context menu for service control
- Notification system
- Quick profile application
- Memory usage optimization
- Auto-start management
"""

import sys
import os
from typing import Dict, List, Optional, Callable
import logging
import time
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSpinBox, QGroupBox, QFormLayout, QTextEdit
)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont

# Import core components
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.process_monitor import default_process_monitor, MonitoringConfig
from core.profile_manager import default_profile_manager
from gui.main_window import WindowResizerMainWindow
from gui.profile_dialog import ProfileManagerDialog
from gui.ui_scale_manager import get_ui_scale_manager

logger = logging.getLogger(__name__)

class TraySettingsDialog(QDialog):
    """Settings dialog for system tray service."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui_scale_manager = get_ui_scale_manager()
        self.setWindowTitle("Background Service Settings")
        self.setModal(True)
        self.resize(400, 300)
        
        self.setup_ui()
        self.load_settings()
        self.ui_scale_manager.register_window(self)
    
    def setup_ui(self):
        """Setup settings dialog UI."""
        layout = QVBoxLayout(self)
        
        # Monitoring settings
        monitor_group = QGroupBox("Process Monitoring")
        monitor_layout = QFormLayout(monitor_group)
        
        self.enabled_checkbox = QCheckBox()
        self.enabled_checkbox.setChecked(True)
        monitor_layout.addRow("Enable Monitoring:", self.enabled_checkbox)
        
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(0, 10)
        self.delay_spinbox.setValue(2)
        self.delay_spinbox.setSuffix(" seconds")
        monitor_layout.addRow("Detection Delay:", self.delay_spinbox)
        
        self.workers_spinbox = QSpinBox()
        self.workers_spinbox.setRange(1, 8)
        self.workers_spinbox.setValue(2)
        monitor_layout.addRow("Worker Threads:", self.workers_spinbox)
        
        layout.addWidget(monitor_group)
        
        # Startup settings
        startup_group = QGroupBox("Startup")
        startup_layout = QFormLayout(startup_group)
        
        self.autostart_checkbox = QCheckBox()
        startup_layout.addRow("Start with Windows:", self.autostart_checkbox)
        
        self.minimize_checkbox = QCheckBox()
        self.minimize_checkbox.setChecked(True)
        startup_layout.addRow("Start Minimized:", self.minimize_checkbox)
        
        layout.addWidget(startup_group)
        
        # Notification settings
        notify_group = QGroupBox("Notifications")
        notify_layout = QFormLayout(notify_group)
        
        self.notify_enabled_checkbox = QCheckBox()
        self.notify_enabled_checkbox.setChecked(True)
        notify_layout.addRow("Show Notifications:", self.notify_enabled_checkbox)
        
        self.notify_profiles_checkbox = QCheckBox()
        self.notify_profiles_checkbox.setChecked(True)
        notify_layout.addRow("Profile Applications:", self.notify_profiles_checkbox)
        
        layout.addWidget(notify_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def load_settings(self):
        """Load current settings."""
        # In a real implementation, load from registry or config file
        pass
    
    def get_config(self) -> MonitoringConfig:
        """Get monitoring configuration from dialog."""
        return MonitoringConfig(
            enabled=self.enabled_checkbox.isChecked(),
            detection_delay=self.delay_spinbox.value(),
            worker_threads=self.workers_spinbox.value()
        )

class TrayStatusDialog(QDialog):
    """Status dialog showing service information."""
    
    def __init__(self, tray_manager, parent=None):
        super().__init__(parent)
        self.ui_scale_manager = get_ui_scale_manager()
        self.tray_manager = tray_manager
        self.setWindowTitle("Service Status")
        self.setModal(False)
        self.resize(500, 400)
        
        self.setup_ui()
        self.ui_scale_manager.register_window(self)
        self.ui_scale_manager.scale_changed.connect(self.apply_ui_scale)
        self.apply_ui_scale(self.ui_scale_manager.scale_percent)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(2000)  # Update every 2 seconds
    
    def setup_ui(self):
        """Setup status dialog UI."""
        layout = QVBoxLayout(self)
        
        # Status display
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setFont(QFont("Consolas", self.ui_scale_manager.scale_value(9)))
        layout.addWidget(self.status_text)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_service)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_service)
        button_layout.addWidget(self.stop_button)
        
        self.restart_button = QPushButton("Restart")
        self.restart_button.clicked.connect(self.restart_service)
        button_layout.addWidget(self.restart_button)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        self.update_status()

    def apply_ui_scale(self, _scale_percent):
        """Keep the explicit monospaced status font in sync with UI scale."""
        self.status_text.setFont(QFont("Consolas", self.ui_scale_manager.scale_value(9)))
    
    def update_status(self):
        """Update status display."""
        try:
            stats = default_process_monitor.get_statistics()
            profile_stats = default_profile_manager.get_statistics()
            
            status_text = f"""창모드 리사이저 0.01.4 상태
{'=' * 50}

Process Monitor:
  Status: {'Running' if stats['is_running'] else 'Stopped'}
  Uptime: {stats.get('uptime', 0):.1f} seconds
  Events Processed: {stats.get('events_processed', 0)}
  Profiles Applied: {stats.get('profiles_applied', 0)}
  Errors: {stats.get('errors', 0)}
  Queue Size: {stats.get('queue_size', 0)}
  Memory Usage: {stats.get('memory_usage', 0):.1f} MB

Profile Manager:
  Total Profiles: {profile_stats.get('total', 0)}
  Enabled Profiles: {profile_stats.get('enabled', 0)}
  Auto-Apply Profiles: {profile_stats.get('auto_apply', 0)}
  Total Applications: {profile_stats.get('total_applications', 0)}

Last Update: {time.strftime('%H:%M:%S')}
"""
            
            self.status_text.setPlainText(status_text)
            
            # Update button states
            is_running = stats['is_running']
            self.start_button.setEnabled(not is_running)
            self.stop_button.setEnabled(is_running)
            self.restart_button.setEnabled(True)
            
        except Exception as e:
            self.status_text.setPlainText(f"Error getting status: {e}")
    
    def start_service(self):
        """Start monitoring service."""
        if default_process_monitor.start():
            self.tray_manager.show_notification("Service Started", "Background monitoring is now active")
    
    def stop_service(self):
        """Stop monitoring service.""" 
        default_process_monitor.stop()
        self.tray_manager.show_notification("Service Stopped", "Background monitoring has been stopped")
    
    def restart_service(self):
        """Restart monitoring service."""
        default_process_monitor.stop()
        time.sleep(0.5)
        if default_process_monitor.start():
            self.tray_manager.show_notification("Service Restarted", "Background monitoring has been restarted")
    
    def closeEvent(self, event):
        """Handle dialog close."""
        self.update_timer.stop()
        event.accept()

class SystemTrayManager:
    """Manages system tray icon and background service."""
    
    def __init__(self):
        """Initialize system tray manager."""
        self.app = None
        self.tray_icon = None
        self.main_window = None
        self.profile_dialog = None
        self.settings_dialog = None
        self.status_dialog = None
        
        # Notification settings
        self.show_notifications = True
        self.show_profile_notifications = True
        
        logger.info("SystemTrayManager initialized")
    
    def initialize(self, app: QApplication) -> bool:
        """Initialize system tray with application."""
        self.app = app
        
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "System Tray", 
                               "System tray is not available on this system.")
            return False
        
        # Create tray icon
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(self.create_tray_icon("idle"))
        self.tray_icon.setToolTip("창모드 리사이저 0.01.4")
        
        # Create context menu
        self.create_context_menu()
        
        # Connect signals
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.messageClicked.connect(self.on_notification_clicked)
        
        # Setup process monitor callbacks
        default_process_monitor.add_event_callback(self.on_process_event)
        default_process_monitor.add_profile_callback(self.on_profile_applied)
        
        # Show tray icon
        self.tray_icon.show()
        
        logger.info("System tray initialized successfully")
        return True
    
    def create_tray_icon(self, status: str = "idle") -> QIcon:
        """Create tray icon with status indicator."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Base icon (window shape)
        if status == "active":
            painter.setBrush(QColor(34, 139, 34))  # Green
        elif status == "error":
            painter.setBrush(QColor(220, 20, 60))  # Red
        else:
            painter.setBrush(QColor(70, 130, 180))  # Blue
        
        painter.drawRoundedRect(4, 4, 24, 24, 4, 4)
        
        # Inner window
        painter.setBrush(QColor(255, 255, 255, 180))
        painter.drawRoundedRect(8, 8, 16, 16, 2, 2)
        
        # Status indicator
        if status == "active":
            painter.setBrush(QColor(34, 139, 34))
            painter.drawEllipse(20, 20, 8, 8)
        elif status == "error":
            painter.setBrush(QColor(220, 20, 60))
            painter.drawEllipse(20, 20, 8, 8)
        
        painter.end()
        return QIcon(pixmap)
    
    def create_context_menu(self):
        """Create system tray context menu."""
        menu = QMenu()
        
        # Service control
        self.start_action = QAction("Start Service", self.app)
        self.start_action.triggered.connect(self.start_service)
        menu.addAction(self.start_action)
        
        self.stop_action = QAction("Stop Service", self.app)
        self.stop_action.triggered.connect(self.stop_service)
        menu.addAction(self.stop_action)
        
        menu.addSeparator()
        
        # Main application
        show_action = QAction("창모드 리사이저 열기", self.app)
        show_action.triggered.connect(self.show_main_window)
        menu.addAction(show_action)
        
        profiles_action = QAction("Manage Profiles", self.app)
        profiles_action.triggered.connect(self.show_profile_manager)
        menu.addAction(profiles_action)
        
        menu.addSeparator()
        
        # Status and settings
        status_action = QAction("Service Status", self.app)
        status_action.triggered.connect(self.show_status_dialog)
        menu.addAction(status_action)
        
        settings_action = QAction("Settings", self.app)
        settings_action.triggered.connect(self.show_settings_dialog)
        menu.addAction(settings_action)
        
        menu.addSeparator()
        
        # Quick profile actions
        profiles_menu = menu.addMenu("Quick Apply")
        self.populate_profiles_menu(profiles_menu)
        
        menu.addSeparator()
        
        # Exit
        exit_action = QAction("Exit", self.app)
        exit_action.triggered.connect(self.exit_application)
        menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(menu)
        self.context_menu = menu
    
    def populate_profiles_menu(self, menu: QMenu):
        """Populate quick profile application menu."""
        menu.clear()
        
        try:
            profiles = default_profile_manager.list_profiles(enabled_only=True)
            
            if not profiles:
                no_profiles_action = QAction("No profiles available", self.app)
                no_profiles_action.setEnabled(False)
                menu.addAction(no_profiles_action)
                return
            
            for profile in profiles[:10]:  # Limit to 10 profiles
                action = QAction(f"{profile.name}", self.app)
                action.setData(profile.id)
                action.triggered.connect(lambda checked, pid=profile.id: self.apply_profile_quick(pid))
                menu.addAction(action)
                
        except Exception as e:
            logger.error(f"Error populating profiles menu: {e}")
    
    def update_service_status(self):
        """Update service status and tray icon."""
        try:
            stats = default_process_monitor.get_statistics()
            
            if stats['is_running']:
                if stats['errors'] > stats.get('last_error_count', 0):
                    self.tray_icon.setIcon(self.create_tray_icon("error"))
                    self.tray_icon.setToolTip("창모드 리사이저 0.01.4 (오류)")
                else:
                    self.tray_icon.setIcon(self.create_tray_icon("active"))
                    self.tray_icon.setToolTip("창모드 리사이저 0.01.4 (작동 중)")
                
                self.start_action.setEnabled(False)
                self.stop_action.setEnabled(True)
            else:
                self.tray_icon.setIcon(self.create_tray_icon("idle"))
                self.tray_icon.setToolTip("창모드 리사이저 0.01.4 (중지됨)")
                
                self.start_action.setEnabled(True)
                self.stop_action.setEnabled(False)
                
        except Exception as e:
            logger.error(f"Error updating service status: {e}")
    
    def start_service(self):
        """Start background monitoring service."""
        if default_process_monitor.start():
            self.show_notification("Service Started", "Background monitoring is now active")
            self.update_service_status()
        else:
            self.show_notification("Service Error", "Failed to start background monitoring", 
                                 QSystemTrayIcon.Critical)
    
    def stop_service(self):
        """Stop background monitoring service."""
        default_process_monitor.stop()
        self.show_notification("Service Stopped", "Background monitoring has been stopped")
        self.update_service_status()
    
    def show_main_window(self):
        """창모드 리사이저 메인 창을 보여줍니다."""
        try:
            if self.main_window is None:
                self.main_window = WindowResizerMainWindow()
            
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
            
        except Exception as e:
            logger.error(f"Error showing main window: {e}")
            self.show_notification("Error", f"Failed to open main window: {e}", 
                                 QSystemTrayIcon.Critical)
    
    def show_profile_manager(self):
        """Show profile manager dialog."""
        try:
            if self.profile_dialog is None:
                self.profile_dialog = ProfileManagerDialog()
            
            self.profile_dialog.show()
            self.profile_dialog.raise_()
            self.profile_dialog.activateWindow()
            
        except Exception as e:
            logger.error(f"Error showing profile manager: {e}")
            self.show_notification("Error", f"Failed to open profile manager: {e}", 
                                 QSystemTrayIcon.Critical)
    
    def show_settings_dialog(self):
        """Show settings dialog."""
        try:
            if self.settings_dialog is None:
                self.settings_dialog = TraySettingsDialog()
            
            if self.settings_dialog.exec_() == QDialog.Accepted:
                config = self.settings_dialog.get_config()
                default_process_monitor.set_config(config)
                self.show_notification("Settings Updated", "Configuration has been applied")
                
        except Exception as e:
            logger.error(f"Error showing settings dialog: {e}")
    
    def show_status_dialog(self):
        """Show service status dialog."""
        try:
            if self.status_dialog is None:
                self.status_dialog = TrayStatusDialog(self)
            
            self.status_dialog.show()
            self.status_dialog.raise_()
            self.status_dialog.activateWindow()
            
        except Exception as e:
            logger.error(f"Error showing status dialog: {e}")
    
    def apply_profile_quick(self, profile_id: str):
        """Quickly apply profile to current active window."""
        try:
            # This would need integration with window detection
            self.show_notification("Quick Apply", 
                                 "Quick profile application not yet implemented")
            
        except Exception as e:
            logger.error(f"Error applying profile quickly: {e}")
    
    def show_notification(self, title: str, message: str, 
                         icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.Information):
        """Show system tray notification."""
        if self.show_notifications and self.tray_icon:
            self.tray_icon.showMessage(title, message, icon, 3000)
    
    def on_tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_main_window()
        elif reason == QSystemTrayIcon.MiddleClick:
            self.show_status_dialog()
    
    def on_notification_clicked(self):
        """Handle notification click."""
        self.show_main_window()
    
    def on_process_event(self, event):
        """Handle process monitor events."""
        # Update tray icon status
        self.update_service_status()
    
    def on_profile_applied(self, profile, window_info):
        """Handle profile application events."""
        if self.show_profile_notifications:
            self.show_notification(
                "Profile Applied",
                f"Applied '{profile.name}' to {window_info.get('title', 'window')}"
            )
    
    def exit_application(self):
        """Exit the application."""
        # Stop monitoring service
        default_process_monitor.stop()
        
        # Close dialogs
        if self.status_dialog:
            self.status_dialog.close()
        if self.settings_dialog:
            self.settings_dialog.close()
        if self.profile_dialog:
            self.profile_dialog.close()
        if self.main_window:
            self.main_window.close()
        
        # Hide tray icon
        if self.tray_icon:
            self.tray_icon.hide()
        
        # Quit application
        if self.app:
            self.app.quit()

# Global system tray manager
default_tray_manager = SystemTrayManager()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray
    
    tray_manager = SystemTrayManager()
    
    if tray_manager.initialize(app):
        # Start the service by default
        tray_manager.start_service()
        
        # Update status periodically
        status_timer = QTimer()
        status_timer.timeout.connect(tray_manager.update_service_status)
        status_timer.start(5000)  # Update every 5 seconds
        
        sys.exit(app.exec_())
    else:
        sys.exit(1)
