"""
Windows API Wrapper Module
==========================

This module provides Python wrappers for essential Windows API functions
used for window enumeration, manipulation, and state management.

Key Features:
- Type-safe API wrappers with proper error handling
- Support for both PyWin32 and ctypes implementations
- Comprehensive exception handling for Win32 errors
- Modern Python typing support
"""

import ctypes
import ctypes.wintypes
from typing import List, Tuple, Optional, Callable, Any
from dataclasses import dataclass
import logging

try:
    import win32api
    import win32gui
    import win32con
    import win32process
    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False
    logging.warning("PyWin32 not available, falling back to ctypes")

# Configure logging
logger = logging.getLogger(__name__)

# Windows API Constants
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_SHOWMAXIMIZED = 3
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5
SW_MINIMIZE = 6
SW_SHOWMINNOACTIVE = 7
SW_SHOWNA = 8
SW_RESTORE = 9

# SetWindowPos flags
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOREDRAW = 0x0008
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040
SWP_HIDEWINDOW = 0x0080

# Special window positions
HWND_TOP = 0
HWND_BOTTOM = 1
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

@dataclass
class WindowRect:
    """Represents a window rectangle with position and size."""
    left: int
    top: int
    right: int
    bottom: int
    
    @property
    def width(self) -> int:
        """Get window width."""
        return self.right - self.left
    
    @property
    def height(self) -> int:
        """Get window height."""
        return self.bottom - self.top
    
    @property
    def x(self) -> int:
        """Get window X position."""
        return self.left
    
    @property
    def y(self) -> int:
        """Get window Y position."""
        return self.top

@dataclass 
class WindowInfo:
    """Contains comprehensive information about a window."""
    hwnd: int
    title: str
    class_name: str
    process_id: int
    thread_id: int
    rect: WindowRect
    is_visible: bool
    is_minimized: bool
    is_maximized: bool

class WindowsAPIError(Exception):
    """Exception raised for Windows API related errors."""
    def __init__(self, message: str, error_code: Optional[int] = None):
        super().__init__(message)
        self.error_code = error_code

class WindowsAPI:
    """
    Windows API wrapper class providing safe access to window management functions.
    
    This class abstracts the complexity of Windows API calls and provides
    a clean Python interface with proper error handling and type safety.
    """
    
    def __init__(self, prefer_pywin32: bool = True):
        """
        Initialize the Windows API wrapper.
        
        Args:
            prefer_pywin32: Whether to prefer PyWin32 over ctypes when available
        """
        self.use_pywin32 = HAS_PYWIN32 and prefer_pywin32
        logger.info(f"Windows API wrapper initialized (using {'PyWin32' if self.use_pywin32 else 'ctypes'})")
        
        if not self.use_pywin32:
            self._setup_ctypes()
    
    def _setup_ctypes(self):
        """Setup ctypes function prototypes for Windows API calls."""
        # Define ctypes prototypes for better type safety
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        
        # EnumWindows callback type
        self.WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        
        # Function prototypes
        self.user32.EnumWindows.argtypes = [self.WNDENUMPROC, ctypes.wintypes.LPARAM]
        self.user32.EnumWindows.restype = ctypes.wintypes.BOOL
        
        self.user32.GetWindowTextW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetWindowTextW.restype = ctypes.c_int
        
        self.user32.GetWindowTextLengthW.argtypes = [ctypes.wintypes.HWND]
        self.user32.GetWindowTextLengthW.restype = ctypes.c_int
        
        self.user32.GetClassNameW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetClassNameW.restype = ctypes.c_int
        
        self.user32.GetWindowRect.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.RECT)]
        self.user32.GetWindowRect.restype = ctypes.wintypes.BOOL
        
        self.user32.SetWindowPos.argtypes = [
            ctypes.wintypes.HWND, ctypes.wintypes.HWND, 
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, 
            ctypes.wintypes.UINT
        ]
        self.user32.SetWindowPos.restype = ctypes.wintypes.BOOL
        
        self.user32.MoveWindow.argtypes = [
            ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_int, 
            ctypes.c_int, ctypes.c_int, ctypes.wintypes.BOOL
        ]
        self.user32.MoveWindow.restype = ctypes.wintypes.BOOL
        
        self.user32.ShowWindow.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
        self.user32.ShowWindow.restype = ctypes.wintypes.BOOL
        
        self.user32.IsWindow.argtypes = [ctypes.wintypes.HWND]
        self.user32.IsWindow.restype = ctypes.wintypes.BOOL
        
        self.user32.IsWindowVisible.argtypes = [ctypes.wintypes.HWND]
        self.user32.IsWindowVisible.restype = ctypes.wintypes.BOOL
        
        self.user32.IsIconic.argtypes = [ctypes.wintypes.HWND]
        self.user32.IsIconic.restype = ctypes.wintypes.BOOL
        
        self.user32.IsZoomed.argtypes = [ctypes.wintypes.HWND]
        self.user32.IsZoomed.restype = ctypes.wintypes.BOOL
        
        self.user32.GetWindowThreadProcessId.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD
    
    def enum_windows(self, callback: Callable[[int, int], bool]) -> bool:
        """
        Enumerate all top-level windows.
        
        Args:
            callback: Function called for each window handle (hwnd, lparam)
            
        Returns:
            True if enumeration completed successfully
            
        Raises:
            WindowsAPIError: If enumeration fails
        """
        try:
            if self.use_pywin32:
                result = win32gui.EnumWindows(callback, 0)
                return bool(result)
            else:
                # ctypes implementation
                def enum_proc(hwnd, lparam):
                    try:
                        return callback(int(hwnd), int(lparam))
                    except Exception as e:
                        logger.error(f"Error in enum callback: {e}")
                        return False
                
                enum_func = self.WNDENUMPROC(enum_proc)
                result = self.user32.EnumWindows(enum_func, 0)
                
                if not result:
                    error_code = ctypes.GetLastError()
                    raise WindowsAPIError(f"EnumWindows failed with error code: {error_code}", error_code)
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to enumerate windows: {e}")
            raise WindowsAPIError(f"Window enumeration failed: {e}")
    
    def get_window_text(self, hwnd: int) -> str:
        """
        Get the text of a window (usually its title).
        
        Args:
            hwnd: Window handle
            
        Returns:
            Window text/title
            
        Raises:
            WindowsAPIError: If unable to get window text
        """
        try:
            if self.use_pywin32:
                return win32gui.GetWindowText(hwnd)
            else:
                # ctypes implementation
                length = self.user32.GetWindowTextLengthW(hwnd)
                if length == 0:
                    return ""
                
                buffer = ctypes.create_unicode_buffer(length + 1)
                result = self.user32.GetWindowTextW(hwnd, buffer, length + 1)
                
                if result == 0:
                    error_code = ctypes.GetLastError()
                    if error_code != 0:  # 0 means no error, just empty title
                        raise WindowsAPIError(f"GetWindowText failed with error: {error_code}", error_code)
                
                return buffer.value
                
        except Exception as e:
            logger.error(f"Failed to get window text for hwnd {hwnd}: {e}")
            return ""  # Return empty string instead of raising exception
    
    def get_class_name(self, hwnd: int) -> str:
        """
        Get the class name of a window.
        
        Args:
            hwnd: Window handle
            
        Returns:
            Window class name
        """
        try:
            if self.use_pywin32:
                return win32gui.GetClassName(hwnd)
            else:
                # ctypes implementation
                buffer = ctypes.create_unicode_buffer(256)
                result = self.user32.GetClassNameW(hwnd, buffer, 256)
                
                if result == 0:
                    error_code = ctypes.GetLastError()
                    raise WindowsAPIError(f"GetClassName failed with error: {error_code}", error_code)
                
                return buffer.value
                
        except Exception as e:
            logger.error(f"Failed to get class name for hwnd {hwnd}: {e}")
            return ""
    
    def get_window_rect(self, hwnd: int) -> WindowRect:
        """
        Get the rectangle coordinates of a window.
        
        Args:
            hwnd: Window handle
            
        Returns:
            WindowRect containing position and size information
            
        Raises:
            WindowsAPIError: If unable to get window rectangle
        """
        try:
            if self.use_pywin32:
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                return WindowRect(left, top, right, bottom)
            else:
                # ctypes implementation
                rect = ctypes.wintypes.RECT()
                result = self.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                
                if not result:
                    error_code = ctypes.GetLastError()
                    raise WindowsAPIError(f"GetWindowRect failed with error: {error_code}", error_code)
                
                return WindowRect(rect.left, rect.top, rect.right, rect.bottom)
                
        except Exception as e:
            logger.error(f"Failed to get window rect for hwnd {hwnd}: {e}")
            raise WindowsAPIError(f"Failed to get window rectangle: {e}")
    
    def set_window_pos(self, hwnd: int, x: int, y: int, width: int, height: int, 
                      flags: int = 0, hwnd_insert_after: int = HWND_TOP) -> bool:
        """
        Set window position and size.
        
        Args:
            hwnd: Window handle
            x: New X position
            y: New Y position  
            width: New width
            height: New height
            flags: SetWindowPos flags
            hwnd_insert_after: Z-order positioning
            
        Returns:
            True if successful
            
        Raises:
            WindowsAPIError: If unable to set window position
        """
        try:
            if self.use_pywin32:
                result = win32gui.SetWindowPos(hwnd, hwnd_insert_after, x, y, width, height, flags)
                return bool(result)
            else:
                # ctypes implementation
                result = self.user32.SetWindowPos(hwnd, hwnd_insert_after, x, y, width, height, flags)
                
                if not result:
                    error_code = ctypes.GetLastError()
                    raise WindowsAPIError(f"SetWindowPos failed with error: {error_code}", error_code)
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to set window position for hwnd {hwnd}: {e}")
            raise WindowsAPIError(f"Failed to set window position: {e}")
    
    def move_window(self, hwnd: int, x: int, y: int, width: int, height: int, repaint: bool = True) -> bool:
        """
        Move and resize a window.
        
        Args:
            hwnd: Window handle
            x: New X position
            y: New Y position
            width: New width
            height: New height
            repaint: Whether to repaint the window
            
        Returns:
            True if successful
            
        Raises:
            WindowsAPIError: If unable to move window
        """
        try:
            if self.use_pywin32:
                try:
                    result = win32gui.MoveWindow(hwnd, x, y, width, height, repaint)
                    # PyWin32 MoveWindow returns None on success, raises exception on error
                    return True
                except Exception as e:
                    logger.debug(f"MoveWindow failed: {e}, trying SetWindowPos")
                    try:
                        win32gui.SetWindowPos(hwnd, 0, x, y, width, height, 0)
                        # PyWin32 SetWindowPos returns None on success, raises exception on error
                        return True
                    except Exception as e2:
                        logger.error(f"Both MoveWindow and SetWindowPos failed: {e2}")
                        return False
            else:
                # ctypes implementation
                result = self.user32.MoveWindow(hwnd, x, y, width, height, repaint)
                
                if not result:
                    # Try with SetWindowPos as fallback
                    logger.debug(f"MoveWindow failed, trying SetWindowPos")
                    result = self.user32.SetWindowPos(
                        hwnd, 0, x, y, width, height, 0
                    )
                    
                    if not result:
                        error_code = ctypes.GetLastError()
                        raise WindowsAPIError(f"Both MoveWindow and SetWindowPos failed with error: {error_code}", error_code)
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to move window hwnd {hwnd}: {e}")
            raise WindowsAPIError(f"Failed to move window: {e}")
    
    def show_window(self, hwnd: int, cmd_show: int) -> bool:
        """
        Show/hide or minimize/maximize a window.
        
        Args:
            hwnd: Window handle
            cmd_show: Show window command (SW_* constants)
            
        Returns:
            True if the window was previously visible
        """
        try:
            if self.use_pywin32:
                return bool(win32gui.ShowWindow(hwnd, cmd_show))
            else:
                # ctypes implementation
                return bool(self.user32.ShowWindow(hwnd, cmd_show))
                
        except Exception as e:
            logger.error(f"Failed to show window hwnd {hwnd}: {e}")
            return False
    
    def is_window(self, hwnd: int) -> bool:
        """Check if a window handle is valid."""
        try:
            if self.use_pywin32:
                return bool(win32gui.IsWindow(hwnd))
            else:
                return bool(self.user32.IsWindow(hwnd))
        except:
            return False
    
    def is_window_visible(self, hwnd: int) -> bool:
        """Check if a window is visible."""
        try:
            if self.use_pywin32:
                return bool(win32gui.IsWindowVisible(hwnd))
            else:
                return bool(self.user32.IsWindowVisible(hwnd))
        except:
            return False
    
    def is_iconic(self, hwnd: int) -> bool:
        """Check if a window is minimized."""
        try:
            if self.use_pywin32:
                return bool(win32gui.IsIconic(hwnd))
            else:
                return bool(self.user32.IsIconic(hwnd))
        except:
            return False
    
    def is_zoomed(self, hwnd: int) -> bool:
        """Check if a window is maximized."""
        try:
            if self.use_pywin32:
                return bool(win32gui.IsZoomed(hwnd))
            else:
                return bool(self.user32.IsZoomed(hwnd))
        except:
            return False
    
    def get_window_thread_process_id(self, hwnd: int) -> Tuple[int, int]:
        """
        Get thread and process ID for a window.
        
        Returns:
            Tuple of (thread_id, process_id)
        """
        try:
            if self.use_pywin32:
                thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
                return thread_id, process_id
            else:
                # ctypes implementation
                process_id = ctypes.wintypes.DWORD()
                thread_id = self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
                return int(thread_id), int(process_id.value)
                
        except Exception as e:
            logger.error(f"Failed to get thread/process ID for hwnd {hwnd}: {e}")
            return 0, 0
    
    def get_window_info(self, hwnd: int) -> Optional[WindowInfo]:
        """
        Get comprehensive information about a window.
        
        Args:
            hwnd: Window handle
            
        Returns:
            WindowInfo object or None if window is invalid
        """
        try:
            if not self.is_window(hwnd):
                return None
            
            title = self.get_window_text(hwnd)
            class_name = self.get_class_name(hwnd)
            rect = self.get_window_rect(hwnd)
            thread_id, process_id = self.get_window_thread_process_id(hwnd)
            
            is_visible = self.is_window_visible(hwnd)
            is_minimized = self.is_iconic(hwnd)
            is_maximized = self.is_zoomed(hwnd)
            
            return WindowInfo(
                hwnd=hwnd,
                title=title,
                class_name=class_name,
                process_id=process_id,
                thread_id=thread_id,
                rect=rect,
                is_visible=is_visible,
                is_minimized=is_minimized,
                is_maximized=is_maximized
            )
            
        except Exception as e:
            logger.error(f"Failed to get window info for hwnd {hwnd}: {e}")
            return None

# Create a default instance
default_api = WindowsAPI()

# Convenience functions using the default instance
def enum_windows(callback: Callable[[int, int], bool]) -> bool:
    """Enumerate all windows using the default API instance."""
    return default_api.enum_windows(callback)

def get_window_text(hwnd: int) -> str:
    """Get window text using the default API instance."""
    return default_api.get_window_text(hwnd)

def get_window_rect(hwnd: int) -> WindowRect:
    """Get window rectangle using the default API instance."""
    return default_api.get_window_rect(hwnd)

def set_window_pos(hwnd: int, x: int, y: int, width: int, height: int, flags: int = 0) -> bool:
    """Set window position using the default API instance."""
    return default_api.set_window_pos(hwnd, x, y, width, height, flags)

def move_window(hwnd: int, x: int, y: int, width: int, height: int, repaint: bool = True) -> bool:
    """Move window using the default API instance."""
    return default_api.move_window(hwnd, x, y, width, height, repaint)

def get_window_info(hwnd: int) -> Optional[WindowInfo]:
    """Get window info using the default API instance."""
    return default_api.get_window_info(hwnd)