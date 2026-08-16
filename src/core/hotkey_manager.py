"""
Global Hotkey Management System
===============================

System-wide hotkey registration and management for quick profile application
and window manipulation. Uses Windows RegisterHotKey API for global shortcuts.

Key Features:
- Global hotkey registration across the entire system
- User-definable key combinations with conflict detection
- Action mapping system for profiles and window operations
- Hotkey persistence and restoration
- Visual key combination display and editing
- Enable/disable toggle functionality
- Multi-monitor and focus-aware operations
"""

import sys
import os
import logging
import ctypes
from ctypes import wintypes
from typing import Dict, List, Optional, Callable, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, IntFlag
import json
import time
import threading
from pathlib import Path

try:
    import win32api
    import win32con
    import win32gui
    from win32gui import RegisterHotKey, UnregisterHotKey
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from PyQt5.QtCore import QObject, pyqtSignal, QAbstractNativeEventFilter
from PyQt5.QtWidgets import QApplication

from core.profile_manager import default_profile_manager
from core.enhanced_window_manipulator import EnhancedWindowManipulator

logger = logging.getLogger(__name__)

class ModifierKeys(IntFlag):
    """Modifier key flags for hotkeys."""
    NONE = 0
    ALT = 0x0001
    CTRL = 0x0002
    SHIFT = 0x0004
    WIN = 0x0008

class HotkeyAction(Enum):
    """Available hotkey actions."""
    APPLY_PROFILE = "apply_profile"
    RELEASE_PROFILE = "release_profile"
    TOGGLE_ALWAYS_ON_TOP = "toggle_always_on_top"
    TOGGLE_AUTO_APPLY = "toggle_auto_apply"
    MINIMIZE_WINDOW = "minimize_window"
    MAXIMIZE_WINDOW = "maximize_window"
    RESTORE_WINDOW = "restore_window"
    CENTER_WINDOW = "center_window"
    MOVE_TO_MONITOR = "move_to_monitor"
    RESIZE_PRESET = "resize_preset"
    LOCK_CURSOR = "lock_cursor"
    UNLOCK_CURSOR = "unlock_cursor"
    SHOW_MAIN_WINDOW = "show_main_window"
    SHOW_PROFILE_MANAGER = "show_profile_manager"
    TOGGLE_SERVICE = "toggle_service"

@dataclass
class HotkeyDefinition:
    """Definition of a hotkey combination and its action."""
    id: str
    name: str
    modifiers: ModifierKeys
    key_code: int
    action: HotkeyAction
    parameters: Dict = field(default_factory=dict)
    enabled: bool = True
    description: str = ""
    
    def __post_init__(self):
        """Validate hotkey definition."""
        if not self.name:
            raise ValueError("Hotkey name cannot be empty")
        if self.key_code < 1 or self.key_code > 255:
            raise ValueError("Invalid key code")
    
    def get_key_combination_text(self) -> str:
        """Get human-readable key combination text."""
        parts = []
        
        if self.modifiers & ModifierKeys.CTRL:
            parts.append("Ctrl")
        if self.modifiers & ModifierKeys.ALT:
            parts.append("Alt")
        if self.modifiers & ModifierKeys.SHIFT:
            parts.append("Shift")
        if self.modifiers & ModifierKeys.WIN:
            parts.append("Win")
        
        # Convert key code to readable name
        key_name = self._get_key_name(self.key_code)
        parts.append(key_name)
        
        return " + ".join(parts)
    
    def _get_key_name(self, key_code: int) -> str:
        """Convert virtual key code to readable name."""
        key_names = {
            # Function keys
            0x70: "F1", 0x71: "F2", 0x72: "F3", 0x73: "F4",
            0x74: "F5", 0x75: "F6", 0x76: "F7", 0x77: "F8",
            0x78: "F9", 0x79: "F10", 0x7A: "F11", 0x7B: "F12",
            
            # Number keys
            0x30: "0", 0x31: "1", 0x32: "2", 0x33: "3", 0x34: "4",
            0x35: "5", 0x36: "6", 0x37: "7", 0x38: "8", 0x39: "9",
            
            # Letter keys
            0x41: "A", 0x42: "B", 0x43: "C", 0x44: "D", 0x45: "E",
            0x46: "F", 0x47: "G", 0x48: "H", 0x49: "I", 0x4A: "J",
            0x4B: "K", 0x4C: "L", 0x4D: "M", 0x4E: "N", 0x4F: "O",
            0x50: "P", 0x51: "Q", 0x52: "R", 0x53: "S", 0x54: "T",
            0x55: "U", 0x56: "V", 0x57: "W", 0x58: "X", 0x59: "Y",
            0x5A: "Z",
            
            # Special keys
            0x20: "Space", 0x0D: "Enter", 0x1B: "Esc", 0x09: "Tab",
            0x08: "Backspace", 0x2E: "Delete", 0x24: "Home", 0x23: "End",
            0x21: "Page Up", 0x22: "Page Down",
            0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
            
            # Numpad keys
            0x60: "Num 0", 0x61: "Num 1", 0x62: "Num 2", 0x63: "Num 3",
            0x64: "Num 4", 0x65: "Num 5", 0x66: "Num 6", 0x67: "Num 7",
            0x68: "Num 8", 0x69: "Num 9",
            
            # Other keys
            0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".",
            0xBF: "/", 0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]",
            0xDE: "'", 0x6A: "Num *", 0x6B: "Num +", 0x6D: "Num -",
            0x6E: "Num .", 0x6F: "Num /"
        }
        
        return key_names.get(key_code, f"Key{key_code}")


def parse_hotkey_combination(combination: str) -> Tuple[ModifierKeys, int]:
    """Convert a profile editor shortcut string into Win32 registration values."""
    if not isinstance(combination, str) or not combination.strip():
        raise ValueError("Hotkey combination is empty")

    modifier_names = {
        "ctrl": ModifierKeys.CTRL,
        "alt": ModifierKeys.ALT,
        "shift": ModifierKeys.SHIFT,
        "win": ModifierKeys.WIN,
    }
    special_key_codes = {
        "space": 0x20,
        "enter": 0x0D,
        "tab": 0x09,
        "backspace": 0x08,
        "delete": 0x2E,
        "home": 0x24,
        "end": 0x23,
        "page up": 0x21,
        "page down": 0x22,
        "left": 0x25,
        "up": 0x26,
        "right": 0x27,
        "down": 0x28,
        "insert": 0x2D,
        "escape": 0x1B,
        "esc": 0x1B,
    }

    modifiers = ModifierKeys.NONE
    key_code = None
    for part in combination.split("+"):
        key_name = part.strip()
        normalized_name = key_name.casefold()
        modifier = modifier_names.get(normalized_name)
        if modifier is not None:
            if modifiers & modifier:
                raise ValueError(f"Duplicate modifier in hotkey: {key_name}")
            modifiers |= modifier
            continue

        if key_code is not None:
            raise ValueError("A hotkey must contain exactly one main key")

        if len(key_name) == 1 and key_name.isalnum():
            key_code = ord(key_name.upper())
        elif normalized_name.startswith("f") and normalized_name[1:].isdigit():
            function_key = int(normalized_name[1:])
            if 1 <= function_key <= 24:
                key_code = 0x6F + function_key
            else:
                raise ValueError(f"Unsupported function key: {key_name}")
        elif normalized_name in special_key_codes:
            key_code = special_key_codes[normalized_name]
        else:
            raise ValueError(f"Unsupported hotkey key: {key_name}")

    if key_code is None:
        raise ValueError("A hotkey must include a main key")

    return modifiers, key_code


class WindowsHotkeyEventFilter(QAbstractNativeEventFilter):
    """Dispatch thread-level WM_HOTKEY messages before Qt consumes them."""

    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def nativeEventFilter(self, event_type, message):
        if event_type not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return False, 0

        native_message = ctypes.cast(
            int(message),
            ctypes.POINTER(wintypes.MSG),
        ).contents
        if native_message.message != win32con.WM_HOTKEY:
            return False, 0

        self.manager._dispatch_registered_hotkey(native_message.wParam)
        return True, 0

class HotkeyManager(QObject):
    """Manages global hotkeys for the application."""
    
    # Signals
    hotkey_activated = pyqtSignal(str, str)  # hotkey_id, action
    hotkey_registered = pyqtSignal(str)      # hotkey_id
    hotkey_unregistered = pyqtSignal(str)    # hotkey_id
    hotkey_error = pyqtSignal(str, str)      # hotkey_id, error_message
    
    def __init__(self, include_default_hotkeys: bool = True):
        """Initialize hotkey manager."""
        super().__init__()
        
        if not WIN32_AVAILABLE:
            raise ImportError("win32api is required for hotkey functionality")
        
        self.hotkeys: Dict[str, HotkeyDefinition] = {}
        self.registered_hotkeys: Dict[int, str] = {}  # atom_id -> hotkey_id
        self.action_callbacks: Dict[HotkeyAction, Callable] = {}
        self.next_atom_id = 1
        self.enabled = True
        
        # Initialize window manipulator for actions
        self.window_manipulator = EnhancedWindowManipulator()
        
        # Profile shortcuts use a dedicated manager without these fixed defaults.
        if include_default_hotkeys:
            self._setup_default_hotkeys()
        
        # Setup message handling
        self._setup_message_handling()
        
        logger.info("HotkeyManager initialized")
    
    def _setup_default_hotkeys(self):
        """Setup default hotkey definitions."""
        default_hotkeys = [
            HotkeyDefinition(
                id="show_main",
                name="Show Main Window",
                modifiers=ModifierKeys.CTRL | ModifierKeys.ALT,
                key_code=0x57,  # W
                action=HotkeyAction.SHOW_MAIN_WINDOW,
                description="Show the main WindowResizer window"
            ),
            HotkeyDefinition(
                id="show_profiles",
                name="Show Profile Manager",
                modifiers=ModifierKeys.CTRL | ModifierKeys.ALT,
                key_code=0x50,  # P
                action=HotkeyAction.SHOW_PROFILE_MANAGER,
                description="Open the profile manager dialog"
            ),
            HotkeyDefinition(
                id="toggle_always_on_top",
                name="Toggle Always On Top",
                modifiers=ModifierKeys.CTRL | ModifierKeys.ALT,
                key_code=0x54,  # T
                action=HotkeyAction.TOGGLE_ALWAYS_ON_TOP,
                description="Toggle always-on-top for active window"
            ),
            HotkeyDefinition(
                id="center_window",
                name="Center Window",
                modifiers=ModifierKeys.CTRL | ModifierKeys.ALT,
                key_code=0x43,  # C
                action=HotkeyAction.CENTER_WINDOW,
                description="Center the active window on screen"
            ),
            HotkeyDefinition(
                id="lock_cursor",
                name="Lock Mouse Cursor",
                modifiers=ModifierKeys.CTRL | ModifierKeys.ALT,
                key_code=0x4C,  # L
                action=HotkeyAction.LOCK_CURSOR,
                description="Lock mouse cursor to active window"
            ),
            HotkeyDefinition(
                id="unlock_cursor",
                name="Unlock Mouse Cursor",
                modifiers=ModifierKeys.CTRL | ModifierKeys.ALT,
                key_code=0x55,  # U
                action=HotkeyAction.UNLOCK_CURSOR,
                description="Unlock mouse cursor"
            )
        ]
        
        for hotkey in default_hotkeys:
            self.hotkeys[hotkey.id] = hotkey
    
    def _setup_message_handling(self):
        """Install a Qt native event filter for thread-level hotkey messages."""
        if not WIN32_AVAILABLE:
            return

        app = QApplication.instance()
        if app is None:
            logger.warning("QApplication is required before registering hotkeys")
            self.native_event_filter = None
            return

        self.native_event_filter = WindowsHotkeyEventFilter(self)
        app.installNativeEventFilter(self.native_event_filter)

    def _dispatch_registered_hotkey(self, atom_id):
        """Look up and execute a profile or application hotkey by its atom ID."""
        hotkey_id = self.registered_hotkeys.get(int(atom_id))
        if hotkey_id is not None:
            self._handle_hotkey_activation(hotkey_id)
    
    def register_hotkey(self, hotkey_id: str) -> bool:
        """Register a hotkey for global activation."""
        if not self.enabled or hotkey_id not in self.hotkeys:
            return False
        
        hotkey = self.hotkeys[hotkey_id]
        
        if not hotkey.enabled:
            return False
        
        try:
            atom_id = self.next_atom_id
            self.next_atom_id += 1
            
            # Register the hotkey
            registration_result = RegisterHotKey(
                None,  # Use NULL window handle for global hotkeys
                atom_id,
                int(hotkey.modifiers),
                hotkey.key_code
            )
            
            if registration_result is False:
                error_msg = f"Failed to register hotkey: {hotkey.name}"
                logger.error(error_msg)
                self.hotkey_error.emit(hotkey_id, error_msg)
                return False

            # pywin32 reports Win32 API success with None and raises on failure.
            self.registered_hotkeys[atom_id] = hotkey_id
            logger.info(f"Registered hotkey: {hotkey.name} ({hotkey.get_key_combination_text()})")
            self.hotkey_registered.emit(hotkey_id)
            return True
                
        except Exception as e:
            error_msg = f"Error registering hotkey: {e}"
            logger.error(error_msg)
            self.hotkey_error.emit(hotkey_id, error_msg)
            return False
    
    def unregister_hotkey(self, hotkey_id: str) -> bool:
        """Unregister a hotkey."""
        try:
            # Find the atom_id for this hotkey
            atom_id = None
            for aid, hid in self.registered_hotkeys.items():
                if hid == hotkey_id:
                    atom_id = aid
                    break
            
            if atom_id is None:
                return True  # Already unregistered
            
            unregistration_result = UnregisterHotKey(None, atom_id)
            
            if unregistration_result is False:
                error_msg = f"Failed to unregister hotkey: {hotkey_id}"
                logger.error(error_msg)
                self.hotkey_error.emit(hotkey_id, error_msg)
                return False

            del self.registered_hotkeys[atom_id]
            logger.info(f"Unregistered hotkey: {hotkey_id}")
            self.hotkey_unregistered.emit(hotkey_id)
            return True
                
        except Exception as e:
            error_msg = f"Error unregistering hotkey: {e}"
            logger.error(error_msg)
            self.hotkey_error.emit(hotkey_id, error_msg)
            return False
    
    def register_all_hotkeys(self) -> int:
        """Register all enabled hotkeys."""
        registered_count = 0
        
        for hotkey_id in self.hotkeys:
            if self.register_hotkey(hotkey_id):
                registered_count += 1
        
        logger.info(f"Registered {registered_count}/{len(self.hotkeys)} hotkeys")
        return registered_count
    
    def unregister_all_hotkeys(self) -> int:
        """Unregister all hotkeys."""
        unregistered_count = 0
        
        # Copy the dict to avoid modification during iteration
        hotkey_ids = list(self.registered_hotkeys.values())
        
        for hotkey_id in hotkey_ids:
            if self.unregister_hotkey(hotkey_id):
                unregistered_count += 1
        
        logger.info(f"Unregistered {unregistered_count} hotkeys")
        return unregistered_count
    
    def _handle_hotkey_activation(self, hotkey_id: str):
        """Handle hotkey activation."""
        if not self.enabled or hotkey_id not in self.hotkeys:
            return
        
        hotkey = self.hotkeys[hotkey_id]
        
        logger.debug(f"Hotkey activated: {hotkey.name}")
        
        try:
            # Execute the action
            self._execute_action(hotkey.action, hotkey.parameters)
            
            # Emit signal
            self.hotkey_activated.emit(hotkey_id, hotkey.action.value)
            
        except Exception as e:
            error_msg = f"Error executing hotkey action: {e}"
            logger.error(error_msg)
            self.hotkey_error.emit(hotkey_id, error_msg)
    
    def _execute_action(self, action: HotkeyAction, parameters: Dict):
        """Execute a hotkey action."""
        if action in self.action_callbacks:
            # Use custom callback if registered
            self.action_callbacks[action](parameters)
            return
        
        # Built-in actions
        if action == HotkeyAction.SHOW_MAIN_WINDOW:
            self._show_main_window()
        elif action == HotkeyAction.SHOW_PROFILE_MANAGER:
            self._show_profile_manager()
        elif action == HotkeyAction.TOGGLE_ALWAYS_ON_TOP:
            self._toggle_always_on_top()
        elif action == HotkeyAction.CENTER_WINDOW:
            self._center_window()
        elif action == HotkeyAction.MINIMIZE_WINDOW:
            self._minimize_window()
        elif action == HotkeyAction.MAXIMIZE_WINDOW:
            self._maximize_window()
        elif action == HotkeyAction.RESTORE_WINDOW:
            self._restore_window()
        elif action == HotkeyAction.LOCK_CURSOR:
            self._lock_cursor()
        elif action == HotkeyAction.UNLOCK_CURSOR:
            self._unlock_cursor()
        elif action == HotkeyAction.APPLY_PROFILE:
            profile_id = parameters.get('profile_id')
            if profile_id:
                self._apply_profile(profile_id)
        elif action == HotkeyAction.RESIZE_PRESET:
            width = parameters.get('width', 800)
            height = parameters.get('height', 600)
            self._resize_preset(width, height)
        else:
            logger.warning(f"Unknown action: {action}")
    
    def _get_active_window(self) -> Optional[int]:
        """Get the handle of the currently active window."""
        try:
            return win32gui.GetForegroundWindow()
        except:
            return None
    
    def _show_main_window(self):
        """Show the main application window."""
        try:
            app = QApplication.instance()
            if app:
                # Find main window
                for widget in app.topLevelWidgets():
                    if hasattr(widget, '__class__') and 'MainWindow' in widget.__class__.__name__:
                        widget.show()
                        widget.raise_()
                        widget.activateWindow()
                        break
        except Exception as e:
            logger.error(f"Error showing main window: {e}")
    
    def _show_profile_manager(self):
        """Show the profile manager dialog."""
        try:
            # This would be implemented by connecting to the main application
            logger.info("Profile manager hotkey activated")
        except Exception as e:
            logger.error(f"Error showing profile manager: {e}")
    
    def _toggle_always_on_top(self):
        """Toggle always-on-top for the active window."""
        hwnd = self._get_active_window()
        if hwnd:
            try:
                # Get current extended style
                ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                
                if ex_style & win32con.WS_EX_TOPMOST:
                    # Remove topmost
                    win32gui.SetWindowPos(
                        hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                    )
                else:
                    # Set topmost
                    win32gui.SetWindowPos(
                        hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                    )
                
                logger.info("Toggled always-on-top for active window")
                
            except Exception as e:
                logger.error(f"Error toggling always-on-top: {e}")
    
    def _center_window(self):
        """Center the active window on screen."""
        hwnd = self._get_active_window()
        if hwnd:
            try:
                # Get window rect
                rect = win32gui.GetWindowRect(hwnd)
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                
                # Get screen dimensions
                screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
                screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
                
                # Calculate center position
                x = (screen_width - width) // 2
                y = (screen_height - height) // 2
                
                # Move window
                win32gui.SetWindowPos(
                    hwnd, 0, x, y, 0, 0,
                    win32con.SWP_NOSIZE | win32con.SWP_NOZORDER
                )
                
                logger.info(f"Centered window at ({x}, {y})")
                
            except Exception as e:
                logger.error(f"Error centering window: {e}")
    
    def _minimize_window(self):
        """Minimize the active window."""
        hwnd = self._get_active_window()
        if hwnd:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                logger.info("Minimized active window")
            except Exception as e:
                logger.error(f"Error minimizing window: {e}")
    
    def _maximize_window(self):
        """Maximize the active window."""
        hwnd = self._get_active_window()
        if hwnd:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                logger.info("Maximized active window")
            except Exception as e:
                logger.error(f"Error maximizing window: {e}")
    
    def _restore_window(self):
        """Restore the active window."""
        hwnd = self._get_active_window()
        if hwnd:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                logger.info("Restored active window")
            except Exception as e:
                logger.error(f"Error restoring window: {e}")
    
    def _lock_cursor(self):
        """Lock cursor to the active window (placeholder)."""
        logger.info("Cursor lock hotkey activated")
        # This will be implemented in the cursor control system
    
    def _unlock_cursor(self):
        """Unlock cursor (placeholder)."""
        logger.info("Cursor unlock hotkey activated")
        # This will be implemented in the cursor control system
    
    def _apply_profile(self, profile_id: str):
        """Apply a profile to the active window."""
        hwnd = self._get_active_window()
        if hwnd and profile_id:
            try:
                # Get window info
                rect = win32gui.GetWindowRect(hwnd)
                title = win32gui.GetWindowText(hwnd)
                
                window_info = {
                    'hwnd': hwnd,
                    'title': title,
                    'rect': rect
                }
                
                # Apply profile
                if default_profile_manager.apply_profile(profile_id, window_info):
                    logger.info(f"Applied profile {profile_id} to active window")
                else:
                    logger.error(f"Failed to apply profile {profile_id}")
                    
            except Exception as e:
                logger.error(f"Error applying profile: {e}")
    
    def _resize_preset(self, width: int, height: int):
        """Resize active window to preset dimensions."""
        hwnd = self._get_active_window()
        if hwnd:
            try:
                win32gui.SetWindowPos(
                    hwnd, 0, 0, 0, width, height,
                    win32con.SWP_NOMOVE | win32con.SWP_NOZORDER
                )
                logger.info(f"Resized window to {width}x{height}")
            except Exception as e:
                logger.error(f"Error resizing window: {e}")
    
    def add_hotkey(self, hotkey: HotkeyDefinition) -> bool:
        """Add a new hotkey definition."""
        if hotkey.id in self.hotkeys:
            logger.warning(f"Hotkey {hotkey.id} already exists")
            return False
        
        # Check for conflicts
        if self._has_conflict(hotkey):
            logger.error(f"Hotkey conflict detected for {hotkey.name}")
            return False
        
        self.hotkeys[hotkey.id] = hotkey
        logger.info(f"Added hotkey: {hotkey.name}")
        return True
    
    def remove_hotkey(self, hotkey_id: str) -> bool:
        """Remove a hotkey definition."""
        if hotkey_id not in self.hotkeys:
            return False
        
        # Unregister if currently registered
        self.unregister_hotkey(hotkey_id)
        
        del self.hotkeys[hotkey_id]
        logger.info(f"Removed hotkey: {hotkey_id}")
        return True

    def clear_hotkeys(self):
        """Unregister and remove every managed hotkey definition."""
        self.unregister_all_hotkeys()
        self.hotkeys.clear()
    
    def _has_conflict(self, new_hotkey: HotkeyDefinition) -> bool:
        """Check if a hotkey conflicts with existing ones."""
        for existing in self.hotkeys.values():
            if (existing.modifiers == new_hotkey.modifiers and 
                existing.key_code == new_hotkey.key_code):
                return True
        return False
    
    def set_action_callback(self, action: HotkeyAction, callback: Callable):
        """Set a custom callback for an action."""
        self.action_callbacks[action] = callback
    
    def enable_hotkeys(self):
        """Enable hotkey system."""
        self.enabled = True
        self.register_all_hotkeys()
        logger.info("Hotkeys enabled")
    
    def disable_hotkeys(self):
        """Disable hotkey system."""
        self.enabled = False
        self.unregister_all_hotkeys()
        logger.info("Hotkeys disabled")

    def shutdown(self):
        """Release registrations and remove the native event filter."""
        self.unregister_all_hotkeys()
        app = QApplication.instance()
        if app is not None and getattr(self, 'native_event_filter', None) is not None:
            app.removeNativeEventFilter(self.native_event_filter)
        self.native_event_filter = None
    
    def get_hotkey_list(self) -> List[HotkeyDefinition]:
        """Get list of all hotkeys."""
        return list(self.hotkeys.values())
    
    def get_registered_hotkeys(self) -> List[str]:
        """Get list of currently registered hotkey IDs."""
        return list(self.registered_hotkeys.values())
    
    def save_hotkeys(self, file_path: str = None):
        """Save hotkey configuration to file."""
        if not file_path:
            config_dir = Path.home() / "AppData" / "Local" / "WindowResizer"
            config_dir.mkdir(parents=True, exist_ok=True)
            file_path = config_dir / "hotkeys.json"
        
        try:
            hotkey_data = {}
            for hotkey_id, hotkey in self.hotkeys.items():
                hotkey_data[hotkey_id] = {
                    'name': hotkey.name,
                    'modifiers': int(hotkey.modifiers),
                    'key_code': hotkey.key_code,
                    'action': hotkey.action.value,
                    'parameters': hotkey.parameters,
                    'enabled': hotkey.enabled,
                    'description': hotkey.description
                }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(hotkey_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved hotkeys to {file_path}")
            
        except Exception as e:
            logger.error(f"Error saving hotkeys: {e}")
    
    def load_hotkeys(self, file_path: str = None):
        """Load hotkey configuration from file."""
        if not file_path:
            config_dir = Path.home() / "AppData" / "Local" / "WindowResizer"
            file_path = config_dir / "hotkeys.json"
        
        if not os.path.exists(file_path):
            logger.info("No hotkey configuration file found, using defaults")
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                hotkey_data = json.load(f)
            
            # Clear existing hotkeys except defaults
            self.unregister_all_hotkeys()
            
            for hotkey_id, data in hotkey_data.items():
                try:
                    hotkey = HotkeyDefinition(
                        id=hotkey_id,
                        name=data['name'],
                        modifiers=ModifierKeys(data['modifiers']),
                        key_code=data['key_code'],
                        action=HotkeyAction(data['action']),
                        parameters=data.get('parameters', {}),
                        enabled=data.get('enabled', True),
                        description=data.get('description', '')
                    )
                    
                    self.hotkeys[hotkey_id] = hotkey
                    
                except Exception as e:
                    logger.error(f"Error loading hotkey {hotkey_id}: {e}")
            
            logger.info(f"Loaded {len(self.hotkeys)} hotkeys from {file_path}")
            
        except Exception as e:
            logger.error(f"Error loading hotkeys: {e}")

# Global hotkey manager instance
default_hotkey_manager = None
profile_hotkey_manager = None

def get_hotkey_manager() -> HotkeyManager:
    """Get or create the global hotkey manager."""
    global default_hotkey_manager
    
    if default_hotkey_manager is None:
        if WIN32_AVAILABLE:
            default_hotkey_manager = HotkeyManager()
        else:
            logger.warning("win32api not available, hotkeys disabled")
    
    return default_hotkey_manager


def get_profile_hotkey_manager() -> Optional[HotkeyManager]:
    """Get the dedicated manager used for profile-defined shortcuts."""
    global profile_hotkey_manager

    if profile_hotkey_manager is None:
        if WIN32_AVAILABLE:
            profile_hotkey_manager = HotkeyManager(include_default_hotkeys=False)
        else:
            logger.warning("win32api not available, profile hotkeys disabled")

    return profile_hotkey_manager

if __name__ == "__main__":
    # Test hotkey manager
    import logging
    logging.basicConfig(level=logging.INFO)
    
    if WIN32_AVAILABLE:
        from PyQt5.QtWidgets import QApplication
        
        app = QApplication(sys.argv)
        
        manager = HotkeyManager()
        
        def on_hotkey(hotkey_id, action):
            print(f"Hotkey activated: {hotkey_id} -> {action}")
        
        manager.hotkey_activated.connect(on_hotkey)
        
        # Register all hotkeys
        registered = manager.register_all_hotkeys()
        print(f"Registered {registered} hotkeys")
        
        # List registered hotkeys
        for hotkey in manager.get_hotkey_list():
            print(f"- {hotkey.name}: {hotkey.get_key_combination_text()}")
        
        print("Hotkey manager running. Try the registered hotkeys. Press Ctrl+C to exit.")
        
        try:
            app.exec_()
        except KeyboardInterrupt:
            print("\nExiting...")
        finally:
            manager.unregister_all_hotkeys()
    else:
        print("win32api not available, cannot test hotkeys")
