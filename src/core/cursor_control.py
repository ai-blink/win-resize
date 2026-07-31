"""
Mouse Cursor Control and Confinement System
===========================================

Advanced mouse cursor control system that can confine cursor movement
to specific window areas or release it system-wide.

Key Features:
- Cursor confinement to window boundaries
- Multi-monitor environment support
- Visual confinement area indicators
- Hotkey-based instant release
- Game mode optimization
- Smooth cursor transitions
- Automatic release on application exit
- Custom confinement shapes and areas
"""

import sys
import os
import time
import logging
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
from pathlib import Path

try:
    import win32api
    import win32con
    import win32gui
    from win32gui import GetCursorPos, SetCursorPos
    # Note: ClipCursor and GetClipCursor are in win32api, not win32gui
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QRect
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtCore import Qt

logger = logging.getLogger(__name__)

class ConfinementMode(Enum):
    """Cursor confinement modes."""
    NONE = "none"
    WINDOW = "window"
    CLIENT_AREA = "client_area"
    CUSTOM_RECT = "custom_rect"
    MONITOR = "monitor"
    VIRTUAL_DESKTOP = "virtual_desktop"

class ConfinementState(Enum):
    """Current confinement state."""
    FREE = "free"
    CONFINED = "confined"
    TRANSITIONING = "transitioning"

@dataclass
class ConfinementArea:
    """Defines a cursor confinement area."""
    left: int
    top: int
    right: int
    bottom: int
    mode: ConfinementMode = ConfinementMode.CUSTOM_RECT
    hwnd: Optional[int] = None
    monitor_index: int = 0
    description: str = ""
    
    def __post_init__(self):
        """Validate confinement area."""
        if self.right <= self.left or self.bottom <= self.top:
            raise ValueError("Invalid confinement area dimensions")
    
    def to_rect_tuple(self) -> Tuple[int, int, int, int]:
        """Convert to Windows RECT tuple."""
        return (self.left, self.top, self.right, self.bottom)
    
    def contains_point(self, x: int, y: int) -> bool:
        """Check if point is within confinement area."""
        return (self.left <= x <= self.right and 
                self.top <= y <= self.bottom)
    
    def get_area_size(self) -> Tuple[int, int]:
        """Get area width and height."""
        return (self.right - self.left, self.bottom - self.top)

class CursorIndicator(QWidget):
    """Visual indicator for cursor confinement area."""
    
    def __init__(self, area: ConfinementArea):
        super().__init__()
        self.area = area
        
        # Set window properties
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Position and size
        self.setGeometry(area.left, area.top, 
                        area.right - area.left, 
                        area.bottom - area.top)
        
        # Animation properties
        self.opacity = 1.0
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.start_fade_out_timer()
    
    def paintEvent(self, event):
        """Paint the confinement indicator."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Set pen for border
        pen = QPen(QColor(255, 100, 100, int(200 * self.opacity)))
        pen.setWidth(3)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        
        # Draw border
        painter.drawRect(2, 2, self.width() - 4, self.height() - 4)
        
        # Draw corner indicators
        corner_size = 20
        pen.setStyle(Qt.SolidLine)
        pen.setWidth(2)
        painter.setPen(pen)
        
        # Top-left corner
        painter.drawLine(2, 2, corner_size, 2)
        painter.drawLine(2, 2, 2, corner_size)
        
        # Top-right corner
        painter.drawLine(self.width() - corner_size, 2, self.width() - 2, 2)
        painter.drawLine(self.width() - 2, 2, self.width() - 2, corner_size)
        
        # Bottom-left corner
        painter.drawLine(2, self.height() - 2, corner_size, self.height() - 2)
        painter.drawLine(2, self.height() - corner_size, 2, self.height() - 2)
        
        # Bottom-right corner
        painter.drawLine(self.width() - corner_size, self.height() - 2, 
                        self.width() - 2, self.height() - 2)
        painter.drawLine(self.width() - 2, self.height() - corner_size, 
                        self.width() - 2, self.height() - 2)
    
    def start_fade_out_timer(self):
        """Start timer to fade out the indicator."""
        QTimer.singleShot(2000, self.start_fade_animation)
    
    def start_fade_animation(self):
        """Start fade out animation."""
        self.animation_timer.start(50)  # 50ms intervals
    
    def update_animation(self):
        """Update fade animation."""
        self.opacity -= 0.05
        
        if self.opacity <= 0:
            self.animation_timer.stop()
            self.hide()
            self.deleteLater()
        else:
            self.update()

class CursorController(QObject):
    """Advanced cursor control and confinement system."""
    
    # Signals
    confinement_changed = pyqtSignal(object, object)  # old_state, new_state
    confinement_activated = pyqtSignal(object)        # confinement_area
    confinement_released = pyqtSignal()
    cursor_position_changed = pyqtSignal(int, int)    # x, y
    
    def __init__(self):
        """Initialize cursor controller."""
        super().__init__()
        
        if not WIN32_AVAILABLE:
            raise ImportError("win32api is required for cursor control")
        
        self.current_state = ConfinementState.FREE
        self.current_area: Optional[ConfinementArea] = None
        self.original_clip_rect: Optional[Tuple[int, int, int, int]] = None
        
        # Visual indicators
        self.show_indicators = True
        self.current_indicator: Optional[CursorIndicator] = None
        
        # Monitoring
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._monitor_cursor)
        self.monitor_interval = 100  # ms
        
        # Game mode optimization
        self.game_mode = False
        self.game_mode_processes: List[str] = [
            "game.exe", "steam.exe", "epic.exe", "origin.exe"
        ]
        
        # Callbacks
        self.release_callbacks: List[Callable] = []
        
        logger.info("CursorController initialized")
    
    def get_current_cursor_pos(self) -> Tuple[int, int]:
        """Get current cursor position."""
        if WIN32_AVAILABLE:
            return win32gui.GetCursorPos()
        return (0, 0)
    
    def set_cursor_pos(self, x: int, y: int) -> bool:
        """Set cursor position."""
        if not WIN32_AVAILABLE:
            return False
        
        try:
            win32gui.SetCursorPos(x, y)
            self.cursor_position_changed.emit(x, y)
            return True
        except Exception as e:
            logger.error(f"Error setting cursor position: {e}")
            return False
    
    def confine_to_window(self, hwnd: int, client_area_only: bool = False) -> bool:
        """Confine cursor to a specific window."""
        if not WIN32_AVAILABLE or not win32gui.IsWindow(hwnd):
            return False
        
        try:
            if client_area_only:
                # Get client area
                client_rect = win32gui.GetClientRect(hwnd)
                # Convert to screen coordinates
                top_left = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
                bottom_right = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
                
                area = ConfinementArea(
                    left=top_left[0],
                    top=top_left[1],
                    right=bottom_right[0],
                    bottom=bottom_right[1],
                    mode=ConfinementMode.CLIENT_AREA,
                    hwnd=hwnd,
                    description=f"Client area of window {hwnd}"
                )
            else:
                # Get entire window rect
                window_rect = win32gui.GetWindowRect(hwnd)
                
                area = ConfinementArea(
                    left=window_rect[0],
                    top=window_rect[1],
                    right=window_rect[2],
                    bottom=window_rect[3],
                    mode=ConfinementMode.WINDOW,
                    hwnd=hwnd,
                    description=f"Window {hwnd} ({win32gui.GetWindowText(hwnd)})"
                )
            
            return self._apply_confinement(area)
            
        except Exception as e:
            logger.error(f"Error confining to window {hwnd}: {e}")
            return False
    
    def confine_to_rect(self, left: int, top: int, right: int, bottom: int, 
                       description: str = "") -> bool:
        """Confine cursor to a custom rectangle."""
        try:
            area = ConfinementArea(
                left=left,
                top=top,
                right=right,
                bottom=bottom,
                mode=ConfinementMode.CUSTOM_RECT,
                description=description or f"Custom rect ({left}, {top}, {right}, {bottom})"
            )
            
            return self._apply_confinement(area)
            
        except Exception as e:
            logger.error(f"Error confining to custom rect: {e}")
            return False
    
    def confine_to_monitor(self, monitor_index: int = 0) -> bool:
        """Confine cursor to a specific monitor."""
        if not WIN32_AVAILABLE:
            return False
        
        try:
            # Get monitor information
            monitors = []
            
            def enum_monitors(hmon, hdc, rect, data):
                monitors.append(rect)
                return True
            
            win32api.EnumDisplayMonitors(None, None, enum_monitors)
            
            if monitor_index >= len(monitors):
                logger.error(f"Monitor index {monitor_index} out of range")
                return False
            
            monitor_rect = monitors[monitor_index]
            
            area = ConfinementArea(
                left=monitor_rect[0],
                top=monitor_rect[1],
                right=monitor_rect[2],
                bottom=monitor_rect[3],
                mode=ConfinementMode.MONITOR,
                monitor_index=monitor_index,
                description=f"Monitor {monitor_index}"
            )
            
            return self._apply_confinement(area)
            
        except Exception as e:
            logger.error(f"Error confining to monitor {monitor_index}: {e}")
            return False
    
    def _apply_confinement(self, area: ConfinementArea) -> bool:
        """Apply cursor confinement to the specified area."""
        try:
            # Store original clip rect if not already confined
            if self.current_state == ConfinementState.FREE:
                self.original_clip_rect = win32api.GetClipCursor()
            
            old_state = self.current_state
            self.current_state = ConfinementState.TRANSITIONING
            
            # Apply cursor clipping
            success = win32api.ClipCursor(area.to_rect_tuple())
            
            if success:
                self.current_area = area
                self.current_state = ConfinementState.CONFINED
                
                # Show visual indicator
                if self.show_indicators:
                    self._show_confinement_indicator(area)
                
                # Start monitoring if not already running
                if not self.monitor_timer.isActive():
                    self.monitor_timer.start(self.monitor_interval)
                
                # Emit signals
                self.confinement_changed.emit(old_state, self.current_state)
                self.confinement_activated.emit(area)
                
                logger.info(f"Cursor confined to: {area.description}")
                return True
            else:
                self.current_state = old_state
                logger.error("Failed to apply cursor clipping")
                return False
                
        except Exception as e:
            logger.error(f"Error applying confinement: {e}")
            return False
    
    def release_confinement(self) -> bool:
        """Release cursor confinement."""
        if self.current_state == ConfinementState.FREE:
            return True
        
        try:
            old_state = self.current_state
            self.current_state = ConfinementState.TRANSITIONING
            
            # Restore original clipping or remove all clipping
            if self.original_clip_rect:
                success = win32api.ClipCursor(self.original_clip_rect)
                self.original_clip_rect = None
            else:
                success = win32api.ClipCursor(None)
            
            if success:
                self.current_state = ConfinementState.FREE
                
                # Hide indicator
                if self.current_indicator:
                    self.current_indicator.hide()
                    self.current_indicator.deleteLater()
                    self.current_indicator = None
                
                # Stop monitoring
                self.monitor_timer.stop()
                
                # Call release callbacks
                for callback in self.release_callbacks:
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"Error in release callback: {e}")
                
                # Clear current area
                old_area = self.current_area
                self.current_area = None
                
                # Emit signals
                self.confinement_changed.emit(old_state, self.current_state)
                self.confinement_released.emit()
                
                logger.info("Cursor confinement released")
                return True
            else:
                self.current_state = old_state
                logger.error("Failed to release cursor clipping")
                return False
                
        except Exception as e:
            logger.error(f"Error releasing confinement: {e}")
            return False
    
    def _show_confinement_indicator(self, area: ConfinementArea):
        """Show visual indicator for confinement area."""
        try:
            # Hide existing indicator
            if self.current_indicator:
                self.current_indicator.hide()
                self.current_indicator.deleteLater()
            
            # Create new indicator
            self.current_indicator = CursorIndicator(area)
            self.current_indicator.show()
            
        except Exception as e:
            logger.error(f"Error showing confinement indicator: {e}")
    
    def _monitor_cursor(self):
        """Monitor cursor position and confinement state."""
        if self.current_state != ConfinementState.CONFINED or not self.current_area:
            return
        
        try:
            # Check if window still exists (for window-based confinement)
            if (self.current_area.hwnd and 
                not win32gui.IsWindow(self.current_area.hwnd)):
                logger.info("Confined window no longer exists, releasing confinement")
                self.release_confinement()
                return
            
            # Get current cursor position
            x, y = self.get_current_cursor_pos()
            
            # Check if cursor is still within confinement area
            if not self.current_area.contains_point(x, y):
                # This shouldn't happen if ClipCursor is working correctly
                logger.debug(f"Cursor outside confinement area: ({x}, {y})")
            
            # In game mode, optimize monitoring
            if self.game_mode:
                self.monitor_timer.setInterval(50)  # Faster monitoring
            else:
                self.monitor_timer.setInterval(self.monitor_interval)
                
        except Exception as e:
            logger.error(f"Error monitoring cursor: {e}")
    
    def toggle_confinement(self, hwnd: int = None) -> bool:
        """Toggle confinement state."""
        if self.current_state == ConfinementState.CONFINED:
            return self.release_confinement()
        else:
            if hwnd:
                return self.confine_to_window(hwnd)
            else:
                # Confine to active window
                active_window = win32gui.GetForegroundWindow()
                if active_window:
                    return self.confine_to_window(active_window)
                return False
    
    def is_confined(self) -> bool:
        """Check if cursor is currently confined."""
        return self.current_state == ConfinementState.CONFINED
    
    def get_confinement_info(self) -> Dict:
        """Get current confinement information."""
        return {
            'state': self.current_state,
            'area': self.current_area,
            'original_clip_rect': self.original_clip_rect,
            'game_mode': self.game_mode,
            'show_indicators': self.show_indicators
        }
    
    def set_game_mode(self, enabled: bool):
        """Enable/disable game mode optimization."""
        self.game_mode = enabled
        
        if enabled:
            # Disable visual indicators in game mode
            self.show_indicators = False
            if self.current_indicator:
                self.current_indicator.hide()
        else:
            self.show_indicators = True
        
        logger.info(f"Game mode {'enabled' if enabled else 'disabled'}")
    
    def add_release_callback(self, callback: Callable):
        """Add callback to be called when confinement is released."""
        self.release_callbacks.append(callback)
    
    def remove_release_callback(self, callback: Callable):
        """Remove release callback."""
        if callback in self.release_callbacks:
            self.release_callbacks.remove(callback)
    
    def set_indicator_visibility(self, visible: bool):
        """Set visibility of confinement indicators."""
        self.show_indicators = visible
        
        if not visible and self.current_indicator:
            self.current_indicator.hide()
        elif visible and self.current_state == ConfinementState.CONFINED:
            if self.current_area:
                self._show_confinement_indicator(self.current_area)
    
    def emergency_release(self):
        """Emergency release of all cursor restrictions."""
        try:
            # Force release clipping
            win32api.ClipCursor(None)
            
            # Reset state
            self.current_state = ConfinementState.FREE
            self.current_area = None
            self.original_clip_rect = None
            
            # Hide indicators
            if self.current_indicator:
                self.current_indicator.hide()
                self.current_indicator.deleteLater()
                self.current_indicator = None
            
            # Stop monitoring
            self.monitor_timer.stop()
            
            logger.warning("Emergency cursor release performed")
            
        except Exception as e:
            logger.error(f"Error in emergency release: {e}")
    
    def __del__(self):
        """Cleanup on destruction."""
        try:
            self.emergency_release()
        except:
            pass

# Global cursor controller instance
default_cursor_controller = None

def get_cursor_controller() -> CursorController:
    """Get or create the global cursor controller."""
    global default_cursor_controller
    
    if default_cursor_controller is None:
        if WIN32_AVAILABLE:
            default_cursor_controller = CursorController()
        else:
            logger.warning("win32api not available, cursor control disabled")
    
    return default_cursor_controller

if __name__ == "__main__":
    # Test cursor controller
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    if WIN32_AVAILABLE:
        from PyQt5.QtWidgets import QApplication
        
        app = QApplication(sys.argv)
        
        controller = CursorController()
        
        def on_confinement_change(old_state, new_state):
            print(f"Confinement state changed: {old_state} -> {new_state}")
        
        def on_confinement_activated(area):
            print(f"Cursor confined to: {area.description}")
        
        def on_confinement_released():
            print("Cursor confinement released")
        
        controller.confinement_changed.connect(on_confinement_change)
        controller.confinement_activated.connect(on_confinement_activated)
        controller.confinement_released.connect(on_confinement_released)
        
        # Test with active window
        active_window = win32gui.GetForegroundWindow()
        if active_window:
            print(f"Testing with active window: {win32gui.GetWindowText(active_window)}")
            
            # Confine to window
            print("Confining cursor to active window...")
            controller.confine_to_window(active_window)
            
            # Release after 5 seconds
            QTimer.singleShot(5000, controller.release_confinement)
        
        print("Cursor controller running. Press Ctrl+C to exit.")
        
        try:
            app.exec_()
        except KeyboardInterrupt:
            print("\nExiting...")
        finally:
            controller.emergency_release()
    else:
        print("win32api not available, cannot test cursor control")