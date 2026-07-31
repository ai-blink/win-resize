"""
Advanced Window State Control System
====================================

Comprehensive window state management system for advanced control over
window properties like transparency, focus, click-through, and visibility.

Key Features:
- Window transparency control with smooth transitions
- Always-on-top management with priority levels
- Focus control and prevention
- Click-through mode for overlays
- Window visibility toggle with fade effects
- State change history and undo functionality
- Extended window properties management
- Multi-monitor awareness
"""

import sys
import os
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum, IntFlag
import threading
from pathlib import Path

try:
    import win32api
    import win32con
    import win32gui
    import win32process
    from win32gui import GetWindowLong, SetWindowLong, SetWindowPos, SetLayeredWindowAttributes
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QApplication

logger = logging.getLogger(__name__)

class WindowState(Enum):
    """Window state types."""
    NORMAL = "normal"
    MINIMIZED = "minimized"
    MAXIMIZED = "maximized"
    FULLSCREEN = "fullscreen"
    HIDDEN = "hidden"

class TopMostLevel(Enum):
    """Always-on-top priority levels."""
    NONE = 0
    NORMAL = 1
    HIGH = 2
    SYSTEM = 3

class TransparencyEffect(Enum):
    """Transparency transition effects."""
    INSTANT = "instant"
    FADE = "fade"
    SMOOTH = "smooth"

@dataclass
class WindowProperties:
    """Extended window properties."""
    hwnd: int
    title: str
    class_name: str
    process_id: int
    thread_id: int
    
    # State properties
    is_visible: bool = True
    is_minimized: bool = False
    is_maximized: bool = False
    is_topmost: bool = False
    
    # Extended properties
    transparency: int = 255  # 0-255 (0 = fully transparent)
    click_through: bool = False
    focus_disabled: bool = False
    
    # Style properties
    original_style: int = 0
    original_ex_style: int = 0
    
    # Position and size
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

@dataclass
class StateChange:
    """Record of a window state change for undo functionality."""
    timestamp: float
    hwnd: int
    property_name: str
    old_value: Any
    new_value: Any
    description: str = ""

class WindowStateManager(QObject):
    """Advanced window state management system."""
    
    # Signals
    state_changed = pyqtSignal(int, str, object, object)  # hwnd, property, old_value, new_value
    transparency_changed = pyqtSignal(int, int)           # hwnd, transparency
    topmost_changed = pyqtSignal(int, bool)               # hwnd, is_topmost
    focus_changed = pyqtSignal(int, bool)                 # hwnd, can_focus
    
    def __init__(self):
        """Initialize window state manager."""
        super().__init__()
        
        if not WIN32_AVAILABLE:
            raise ImportError("win32api is required for window state management")
        
        self.window_properties: Dict[int, WindowProperties] = {}
        self.state_history: List[StateChange] = []
        self.max_history_size = 1000
        
        # Animation settings
        self.animation_enabled = True
        self.animation_duration = 300  # milliseconds
        self.animation_steps = 30
        
        # Timers for animations
        self.transparency_timers: Dict[int, QTimer] = {}
        
        logger.info("WindowStateManager initialized")
    
    def get_window_properties(self, hwnd: int) -> Optional[WindowProperties]:
        """Get comprehensive window properties."""
        if not WIN32_AVAILABLE or not hwnd:
            return None
        
        try:
            # Check if window exists
            if not win32gui.IsWindow(hwnd):
                return None
            
            # Get basic info
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
            
            # Get window rect
            rect = win32gui.GetWindowRect(hwnd)
            
            # Get window styles
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            
            # Determine state
            is_visible = win32gui.IsWindowVisible(hwnd)
            is_minimized = bool(style & win32con.WS_MINIMIZE)
            is_maximized = bool(style & win32con.WS_MAXIMIZE)
            is_topmost = bool(ex_style & win32con.WS_EX_TOPMOST)
            
            # Get transparency (if layered window)
            transparency = 255
            if ex_style & win32con.WS_EX_LAYERED:
                try:
                    _, _, alpha = win32gui.GetLayeredWindowAttributes(hwnd)
                    transparency = alpha
                except:
                    pass
            
            # Create properties object
            properties = WindowProperties(
                hwnd=hwnd,
                title=title,
                class_name=class_name,
                process_id=process_id,
                thread_id=thread_id,
                is_visible=is_visible,
                is_minimized=is_minimized,
                is_maximized=is_maximized,
                is_topmost=is_topmost,
                transparency=transparency,
                click_through=bool(ex_style & win32con.WS_EX_TRANSPARENT),
                original_style=style,
                original_ex_style=ex_style,
                x=rect[0],
                y=rect[1],
                width=rect[2] - rect[0],
                height=rect[3] - rect[1]
            )
            
            # Cache properties
            self.window_properties[hwnd] = properties
            
            return properties
            
        except Exception as e:
            logger.error(f"Error getting window properties for {hwnd}: {e}")
            return None
    
    def set_window_transparency(self, hwnd: int, transparency: int, 
                               effect: TransparencyEffect = TransparencyEffect.INSTANT) -> bool:
        """Set window transparency with optional animation."""
        if not WIN32_AVAILABLE or not win32gui.IsWindow(hwnd):
            return False
        
        # Validate transparency value
        transparency = max(0, min(255, transparency))
        
        try:
            # Get current properties
            properties = self.get_window_properties(hwnd)
            if not properties:
                return False
            
            old_transparency = properties.transparency
            
            # Record state change
            self._record_state_change(
                hwnd, "transparency", old_transparency, transparency,
                f"Changed transparency from {old_transparency} to {transparency}"
            )
            
            if effect == TransparencyEffect.INSTANT:
                return self._set_transparency_direct(hwnd, transparency)
            else:
                return self._set_transparency_animated(hwnd, old_transparency, transparency, effect)
            
        except Exception as e:
            logger.error(f"Error setting transparency for {hwnd}: {e}")
            return False
    
    def _set_transparency_direct(self, hwnd: int, transparency: int) -> bool:
        """Set transparency directly without animation."""
        try:
            # Make window layered if not already
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if not (ex_style & win32con.WS_EX_LAYERED):
                win32gui.SetWindowLong(
                    hwnd, win32con.GWL_EXSTYLE, 
                    ex_style | win32con.WS_EX_LAYERED
                )
            
            # Set transparency
            win32gui.SetLayeredWindowAttributes(
                hwnd, 0, transparency, win32con.LWA_ALPHA
            )
            
            # Update cached properties
            if hwnd in self.window_properties:
                self.window_properties[hwnd].transparency = transparency
            
            # Emit signal
            self.transparency_changed.emit(hwnd, transparency)
            
            logger.debug(f"Set transparency for {hwnd} to {transparency}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting direct transparency: {e}")
            return False
    
    def _set_transparency_animated(self, hwnd: int, start: int, end: int, 
                                  effect: TransparencyEffect) -> bool:
        """Set transparency with animation."""
        if not self.animation_enabled:
            return self._set_transparency_direct(hwnd, end)
        
        # Stop any existing animation for this window
        if hwnd in self.transparency_timers:
            self.transparency_timers[hwnd].stop()
            del self.transparency_timers[hwnd]
        
        # Calculate animation parameters
        step_count = self.animation_steps
        step_size = (end - start) / step_count
        step_duration = self.animation_duration // step_count
        
        current_step = 0
        
        def animate_step():
            nonlocal current_step
            
            if current_step >= step_count:
                # Animation complete
                self._set_transparency_direct(hwnd, end)
                if hwnd in self.transparency_timers:
                    del self.transparency_timers[hwnd]
                return
            
            # Calculate current transparency
            if effect == TransparencyEffect.FADE:
                # Linear interpolation
                current_transparency = int(start + (step_size * current_step))
            else:  # SMOOTH
                # Ease-in-out interpolation
                progress = current_step / step_count
                eased_progress = 0.5 * (1 - cos(progress * pi))
                current_transparency = int(start + ((end - start) * eased_progress))
            
            # Set transparency
            self._set_transparency_direct(hwnd, current_transparency)
            
            current_step += 1
        
        # Create and start timer
        timer = QTimer()
        timer.timeout.connect(animate_step)
        timer.start(step_duration)
        
        self.transparency_timers[hwnd] = timer
        
        return True
    
    def set_always_on_top(self, hwnd: int, enabled: bool, 
                          level: TopMostLevel = TopMostLevel.NORMAL) -> bool:
        """Set always-on-top state with priority level."""
        if not WIN32_AVAILABLE or not win32gui.IsWindow(hwnd):
            return False
        
        try:
            properties = self.get_window_properties(hwnd)
            if not properties:
                return False
            
            old_topmost = properties.is_topmost
            
            # Record state change
            self._record_state_change(
                hwnd, "always_on_top", old_topmost, enabled,
                f"{'Enabled' if enabled else 'Disabled'} always-on-top"
            )
            
            if enabled:
                # Set topmost based on level
                if level == TopMostLevel.SYSTEM:
                    insert_after = win32con.HWND_TOPMOST
                elif level == TopMostLevel.HIGH:
                    insert_after = win32con.HWND_TOPMOST
                else:
                    insert_after = win32con.HWND_TOPMOST
            else:
                insert_after = win32con.HWND_NOTOPMOST
            
            # Apply the change
            success = win32gui.SetWindowPos(
                hwnd, insert_after, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            
            if success:
                # Update cached properties
                if hwnd in self.window_properties:
                    self.window_properties[hwnd].is_topmost = enabled
                
                # Emit signal
                self.topmost_changed.emit(hwnd, enabled)
                
                logger.debug(f"Set always-on-top for {hwnd} to {enabled}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error setting always-on-top for {hwnd}: {e}")
            return False
    
    def set_click_through(self, hwnd: int, enabled: bool) -> bool:
        """Enable/disable click-through for window."""
        if not WIN32_AVAILABLE or not win32gui.IsWindow(hwnd):
            return False
        
        try:
            properties = self.get_window_properties(hwnd)
            if not properties:
                return False
            
            old_click_through = properties.click_through
            
            # Record state change
            self._record_state_change(
                hwnd, "click_through", old_click_through, enabled,
                f"{'Enabled' if enabled else 'Disabled'} click-through"
            )
            
            # Get current extended style
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            
            if enabled:
                new_ex_style = ex_style | win32con.WS_EX_TRANSPARENT
            else:
                new_ex_style = ex_style & ~win32con.WS_EX_TRANSPARENT
            
            # Apply the change
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_ex_style)
            
            # Update cached properties
            if hwnd in self.window_properties:
                self.window_properties[hwnd].click_through = enabled
            
            logger.debug(f"Set click-through for {hwnd} to {enabled}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting click-through for {hwnd}: {e}")
            return False
    
    def set_focus_disabled(self, hwnd: int, disabled: bool) -> bool:
        """Enable/disable window focus capability."""
        if not WIN32_AVAILABLE or not win32gui.IsWindow(hwnd):
            return False
        
        try:
            properties = self.get_window_properties(hwnd)
            if not properties:
                return False
            
            old_focus_disabled = properties.focus_disabled
            
            # Record state change
            self._record_state_change(
                hwnd, "focus_disabled", old_focus_disabled, disabled,
                f"{'Disabled' if disabled else 'Enabled'} window focus"
            )
            
            # Get current extended style
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            
            if disabled:
                new_ex_style = ex_style | win32con.WS_EX_NOACTIVATE
            else:
                new_ex_style = ex_style & ~win32con.WS_EX_NOACTIVATE
            
            # Apply the change
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_ex_style)
            
            # Update cached properties
            if hwnd in self.window_properties:
                self.window_properties[hwnd].focus_disabled = disabled
            
            # Emit signal
            self.focus_changed.emit(hwnd, not disabled)
            
            logger.debug(f"Set focus disabled for {hwnd} to {disabled}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting focus disabled for {hwnd}: {e}")
            return False
    
    def toggle_window_visibility(self, hwnd: int, fade: bool = True) -> bool:
        """Toggle window visibility with optional fade effect."""
        if not WIN32_AVAILABLE or not win32gui.IsWindow(hwnd):
            return False
        
        try:
            is_visible = win32gui.IsWindowVisible(hwnd)
            
            if fade and self.animation_enabled:
                if is_visible:
                    # Fade out then hide
                    self.set_window_transparency(hwnd, 0, TransparencyEffect.FADE)
                    QTimer.singleShot(self.animation_duration, 
                                    lambda: win32gui.ShowWindow(hwnd, win32con.SW_HIDE))
                else:
                    # Show then fade in
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                    self.set_window_transparency(hwnd, 255, TransparencyEffect.FADE)
            else:
                # Instant toggle
                if is_visible:
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                else:
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            
            # Record state change
            self._record_state_change(
                hwnd, "visibility", is_visible, not is_visible,
                f"{'Hid' if is_visible else 'Showed'} window"
            )
            
            logger.debug(f"Toggled visibility for {hwnd}")
            return True
            
        except Exception as e:
            logger.error(f"Error toggling visibility for {hwnd}: {e}")
            return False
    
    def restore_original_state(self, hwnd: int) -> bool:
        """Restore window to its original state."""
        if hwnd not in self.window_properties:
            return False
        
        try:
            properties = self.window_properties[hwnd]
            
            # Restore original styles
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, properties.original_style)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, properties.original_ex_style)
            
            # Restore transparency
            self.set_window_transparency(hwnd, 255)
            
            # Remove topmost
            self.set_always_on_top(hwnd, False)
            
            logger.info(f"Restored original state for {hwnd}")
            return True
            
        except Exception as e:
            logger.error(f"Error restoring original state for {hwnd}: {e}")
            return False
    
    def _record_state_change(self, hwnd: int, property_name: str, 
                           old_value: Any, new_value: Any, description: str = ""):
        """Record a state change for undo functionality."""
        change = StateChange(
            timestamp=time.time(),
            hwnd=hwnd,
            property_name=property_name,
            old_value=old_value,
            new_value=new_value,
            description=description
        )
        
        self.state_history.append(change)
        
        # Limit history size
        if len(self.state_history) > self.max_history_size:
            self.state_history.pop(0)
        
        # Emit signal
        self.state_changed.emit(hwnd, property_name, old_value, new_value)
    
    def undo_last_change(self, hwnd: int = None) -> bool:
        """Undo the last state change for a window or globally."""
        if not self.state_history:
            return False
        
        # Find the last change for the specified window (or any window)
        change = None
        for i in range(len(self.state_history) - 1, -1, -1):
            if hwnd is None or self.state_history[i].hwnd == hwnd:
                change = self.state_history.pop(i)
                break
        
        if not change:
            return False
        
        try:
            # Apply the old value
            if change.property_name == "transparency":
                self._set_transparency_direct(change.hwnd, change.old_value)
            elif change.property_name == "always_on_top":
                self.set_always_on_top(change.hwnd, change.old_value)
            elif change.property_name == "click_through":
                self.set_click_through(change.hwnd, change.old_value)
            elif change.property_name == "focus_disabled":
                self.set_focus_disabled(change.hwnd, change.old_value)
            elif change.property_name == "visibility":
                if change.old_value:
                    win32gui.ShowWindow(change.hwnd, win32con.SW_SHOW)
                else:
                    win32gui.ShowWindow(change.hwnd, win32con.SW_HIDE)
            
            logger.info(f"Undid change: {change.description}")
            return True
            
        except Exception as e:
            logger.error(f"Error undoing change: {e}")
            return False
    
    def get_state_history(self, hwnd: int = None) -> List[StateChange]:
        """Get state change history for a window or all windows."""
        if hwnd is None:
            return self.state_history.copy()
        else:
            return [change for change in self.state_history if change.hwnd == hwnd]
    
    def clear_history(self, hwnd: int = None):
        """Clear state change history."""
        if hwnd is None:
            self.state_history.clear()
        else:
            self.state_history = [change for change in self.state_history 
                                if change.hwnd != hwnd]
        
        logger.info(f"Cleared state history{'for window ' + str(hwnd) if hwnd else ''}")
    
    def enable_animations(self, enabled: bool = True):
        """Enable or disable animations."""
        self.animation_enabled = enabled
        logger.info(f"Animations {'enabled' if enabled else 'disabled'}")
    
    def set_animation_duration(self, duration_ms: int):
        """Set animation duration in milliseconds."""
        self.animation_duration = max(100, min(2000, duration_ms))
        logger.info(f"Animation duration set to {self.animation_duration}ms")
    
    def cleanup_window(self, hwnd: int):
        """Clean up resources for a window."""
        # Stop any running animations
        if hwnd in self.transparency_timers:
            self.transparency_timers[hwnd].stop()
            del self.transparency_timers[hwnd]
        
        # Remove from cache
        if hwnd in self.window_properties:
            del self.window_properties[hwnd]
        
        # Clear history
        self.clear_history(hwnd)

# Global window state manager instance
default_window_state_manager = None

def get_window_state_manager() -> WindowStateManager:
    """Get or create the global window state manager."""
    global default_window_state_manager
    
    if default_window_state_manager is None:
        if WIN32_AVAILABLE:
            default_window_state_manager = WindowStateManager()
        else:
            logger.warning("win32api not available, window state management disabled")
    
    return default_window_state_manager

if __name__ == "__main__":
    # Test window state manager
    import logging
    from math import cos, pi
    
    logging.basicConfig(level=logging.INFO)
    
    if WIN32_AVAILABLE:
        from PyQt5.QtWidgets import QApplication
        
        app = QApplication(sys.argv)
        
        manager = WindowStateManager()
        
        def on_state_change(hwnd, property_name, old_value, new_value):
            print(f"State changed for {hwnd}: {property_name} {old_value} -> {new_value}")
        
        manager.state_changed.connect(on_state_change)
        
        # Get active window for testing
        active_window = win32gui.GetForegroundWindow()
        if active_window:
            print(f"Testing with active window: {active_window}")
            
            # Get properties
            props = manager.get_window_properties(active_window)
            if props:
                print(f"Window: {props.title}")
                print(f"Transparency: {props.transparency}")
                print(f"Always on top: {props.is_topmost}")
                
                # Test transparency animation
                print("Setting transparency to 128...")
                manager.set_window_transparency(active_window, 128, TransparencyEffect.FADE)
                
                # Restore after 3 seconds
                QTimer.singleShot(3000, lambda: manager.set_window_transparency(active_window, 255))
        
        print("Window state manager running. Press Ctrl+C to exit.")
        
        try:
            app.exec_()
        except KeyboardInterrupt:
            print("\nExiting...")
    else:
        print("win32api not available, cannot test window state management")