"""
Advanced Window Manipulation System
===================================

Provides sophisticated window manipulation capabilities including:
- Advanced positioning and sizing with multi-monitor support
- DPI-aware coordinate calculations
- Window state management (minimize/maximize/restore)
- Boundary validation and constraint enforcement
- Animation and smooth transitions
- Rollback capabilities for failed operations

Key Features:
- Multi-monitor coordinate system handling
- DPI scaling compensation
- Window constraint validation
- State preservation and restoration
- Error recovery and rollback
"""

import ctypes
from ctypes import wintypes, windll
import time
import threading
from typing import Dict, List, Optional, Tuple, NamedTuple, Union
from dataclasses import dataclass, field
from enum import Enum, IntFlag
import logging

from .windows_api import WindowsAPI, WindowInfo, WindowRect, WindowsAPIError

logger = logging.getLogger(__name__)

# Game Engine Detection Patterns
GAME_ENGINE_PATTERNS = {
    'unity': ['Unity', 'UnityEngine', 'Unity Player', 'Made with Unity'],
    'unreal': ['UE4', 'UE5', 'UnrealEngine', 'Unreal Engine'],
    'directx': ['DirectX', 'D3D', 'Direct3D'],
    'opengl': ['OpenGL', 'GL'],
    'vulkan': ['Vulkan', 'VK'],
    'custom': ['Custom', 'Proprietary', 'Independent']
}

# Window Style Constants for Stubborn Games
WS_OVERLAPPED = 0x00000000
WS_POPUP = 0x80000000
WS_CHILD = 0x40000000
WS_MINIMIZE = 0x20000000
WS_VISIBLE = 0x10000000
WS_DISABLED = 0x08000000
WS_CLIPSIBLINGS = 0x04000000
WS_CLIPCHILDREN = 0x02000000
WS_MAXIMIZE = 0x01000000
WS_CAPTION = 0x00C00000
WS_BORDER = 0x00800000
WS_DLGFRAME = 0x00400000
WS_VSCROLL = 0x00200000
WS_HSCROLL = 0x00100000
WS_SYSMENU = 0x00080000
WS_THICKFRAME = 0x00040000
WS_GROUP = 0x00020000
WS_TABSTOP = 0x00010000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_OVERLAPPEDWINDOW = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX

# Extended Window Styles
WS_EX_DLGMODALFRAME = 0x00000001
WS_EX_NOPARENTNOTIFY = 0x00000004
WS_EX_TOPMOST = 0x00000008
WS_EX_ACCEPTFILES = 0x00000010
WS_EX_TRANSPARENT = 0x00000020
WS_EX_MDICHILD = 0x00000040
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_WINDOWEDGE = 0x00000100
WS_EX_CLIENTEDGE = 0x00000200
WS_EX_CONTEXTHELP = 0x00000400
WS_EX_RIGHT = 0x00001000
WS_EX_LEFT = 0x00000000
WS_EX_RTLREADING = 0x00002000
WS_EX_LTRREADING = 0x00000000
WS_EX_LEFTSCROLLBAR = 0x00004000
WS_EX_RIGHTSCROLLBAR = 0x00000000
WS_EX_CONTROLPARENT = 0x00010000
WS_EX_STATICEDGE = 0x00020000
WS_EX_APPWINDOW = 0x00040000
WS_EX_OVERLAPPEDWINDOW = WS_EX_WINDOWEDGE | WS_EX_CLIENTEDGE
WS_EX_PALETTEWINDOW = WS_EX_WINDOWEDGE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST

class WindowState(Enum):
    """Window state constants."""
    NORMAL = 1
    MINIMIZED = 2
    MAXIMIZED = 3
    HIDDEN = 4
    RESTORE = 9

class WindowPosition(IntFlag):
    """Window positioning flags."""
    NOMOVE = 0x0002
    NOSIZE = 0x0001
    NOZORDER = 0x0004
    NOREDRAW = 0x0008
    NOACTIVATE = 0x0010
    FRAMECHANGED = 0x0020
    SHOWWINDOW = 0x0040
    HIDEWINDOW = 0x0080
    NOCOPYBITS = 0x0100
    NOOWNERZORDER = 0x0200
    NOSENDCHANGING = 0x0400

@dataclass
class GameEngineInfo:
    """Information about detected game engine."""
    engine_type: str
    confidence: float
    window_style: int
    extended_style: int
    requires_special_handling: bool = False
    supports_resize: bool = True
    supports_move: bool = True

@dataclass
class MonitorInfo:
    """Information about a monitor."""
    handle: int
    rect: WindowRect
    work_rect: WindowRect
    is_primary: bool
    device_name: str
    dpi_x: int = 96
    dpi_y: int = 96
    scale_factor: float = 1.0

@dataclass
class WindowConstraints:
    """Constraints for window positioning and sizing."""
    min_width: int = 100
    min_height: int = 100
    max_width: Optional[int] = None
    max_height: Optional[int] = None
    keep_on_screen: bool = True
    respect_work_area: bool = True
    maintain_aspect_ratio: bool = False
    aspect_ratio: Optional[float] = None

@dataclass
class WindowOperation:
    """Information about a window operation for rollback."""
    hwnd: int
    operation_type: str
    original_rect: WindowRect
    original_state: WindowState
    timestamp: float = field(default_factory=time.time)
    success: bool = False

class WindowManipulator:
    """
    Advanced window manipulation system with multi-monitor and DPI support.
    
    Provides comprehensive window positioning, sizing, and state management
    with proper error handling and rollback capabilities.
    """
    
    def __init__(self):
        """Initialize the window manipulator."""
        self.api = WindowsAPI()
        self._monitors: Dict[int, MonitorInfo] = {}
        self._operation_history: List[WindowOperation] = []
        self._max_history = 100
        self._lock = threading.RLock()
        
        # Initialize monitor information
        self._update_monitor_info()
        
        logger.debug("Window manipulator initialized")
    
    def move_window(self, 
                   hwnd: int, 
                   x: int, 
                   y: int, 
                   width: Optional[int] = None, 
                   height: Optional[int] = None,
                   constraints: Optional[WindowConstraints] = None,
                   animate: bool = False) -> bool:
        """
        Move and/or resize a window with advanced options.
        
        Args:
            hwnd: Window handle
            x: New X coordinate
            y: New Y coordinate  
            width: New width (None to keep current)
            height: New height (None to keep current)
            constraints: Window positioning constraints
            animate: Whether to animate the movement
            
        Returns:
            True if successful
        """
        with self._lock:
            try:
                # Get current window information
                current_rect = self.api.get_window_rect(hwnd)
                if not current_rect:
                    return False
                
                # Record operation for potential rollback
                operation = WindowOperation(
                    hwnd=hwnd,
                    operation_type="move_window",
                    original_rect=current_rect,
                    original_state=self._get_window_state(hwnd)
                )
                
                # Use current dimensions if not specified
                if width is None:
                    width = current_rect.width
                if height is None:
                    height = current_rect.height
                
                # Apply constraints
                if constraints:
                    x, y, width, height = self._apply_constraints(
                        x, y, width, height, constraints
                    )
                
                # Convert coordinates for DPI scaling
                x, y = self._scale_coordinates_to_physical(x, y)
                width, height = self._scale_size_to_physical(width, height)
                
                # Perform the move operation
                if animate:
                    success = self._animate_window_move(
                        hwnd, current_rect, Rectangle(x, y, width, height)
                    )
                else:
                    success = self.api.move_window(hwnd, x, y, width, height, True)
                
                operation.success = success
                self._add_operation_to_history(operation)
                
                if success:
                    logger.debug(f"Successfully moved window {hwnd} to ({x}, {y}) size {width}x{height}")
                else:
                    logger.warning(f"창 이동에 실패했습니다 (ID: {hwnd}). 일부 창은 관리자 권한이 필요할 수 있습니다.")
                
                return success
                
            except Exception as e:
                logger.error(f"Error moving window {hwnd}: {e}")
                return False
    
    def resize_window(self,
                     hwnd: int,
                     width: int,
                     height: int,
                     constraints: Optional[WindowConstraints] = None,
                     maintain_position: bool = True) -> bool:
        """
        Resize a window while optionally maintaining its position.
        
        Args:
            hwnd: Window handle
            width: New width
            height: New height
            constraints: Resize constraints
            maintain_position: Whether to keep the window position
            
        Returns:
            True if successful
        """
        try:
            current_rect = self.api.get_window_rect(hwnd)
            if not current_rect:
                return False
            
            x = current_rect.left if maintain_position else current_rect.left
            y = current_rect.top if maintain_position else current_rect.top
            
            return self.move_window(hwnd, x, y, width, height, constraints)
            
        except Exception as e:
            logger.error(f"Error resizing window {hwnd}: {e}")
            return False
    
    def center_window(self,
                     hwnd: int,
                     monitor_handle: Optional[int] = None,
                     work_area: bool = True) -> bool:
        """
        Center a window on a specific monitor or the primary monitor.
        
        Args:
            hwnd: Window handle
            monitor_handle: Specific monitor (None for primary)
            work_area: Center within work area (excluding taskbar)
            
        Returns:
            True if successful
        """
        try:
            window_rect = self.api.get_window_rect(hwnd)
            if not window_rect:
                return False
            
            # Get target monitor
            if monitor_handle is None:
                monitor = self._get_primary_monitor()
            else:
                monitor = self._monitors.get(monitor_handle)
            
            if not monitor:
                return False
            
            # Choose centering area
            center_rect = monitor.work_rect if work_area else monitor.rect
            
            # Calculate center position
            center_x = center_rect.left + (center_rect.width - window_rect.width) // 2
            center_y = center_rect.top + (center_rect.height - window_rect.height) // 2
            
            return self.move_window(hwnd, center_x, center_y)
            
        except Exception as e:
            logger.error(f"Error centering window {hwnd}: {e}")
            return False
    
    def set_window_state(self, hwnd: int, state: WindowState) -> bool:
        """
        Set window state (minimize, maximize, restore, etc.).
        
        Args:
            hwnd: Window handle
            state: Target window state
            
        Returns:
            True if successful
        """
        try:
            # Record current state for rollback
            current_state = self._get_window_state(hwnd)
            current_rect = self.api.get_window_rect(hwnd)
            
            operation = WindowOperation(
                hwnd=hwnd,
                operation_type="set_window_state",
                original_rect=current_rect or WindowRect(0, 0, 0, 0),
                original_state=current_state
            )
            
            # Map state to ShowWindow command
            show_commands = {
                WindowState.NORMAL: 1,    # SW_SHOWNORMAL
                WindowState.MINIMIZED: 2, # SW_SHOWMINIMIZED
                WindowState.MAXIMIZED: 3, # SW_SHOWMAXIMIZED
                WindowState.HIDDEN: 0,    # SW_HIDE
                WindowState.RESTORE: 9    # SW_RESTORE
            }
            
            command = show_commands.get(state)
            if command is None:
                return False
            
            success = bool(windll.user32.ShowWindow(hwnd, command))
            operation.success = success
            self._add_operation_to_history(operation)
            
            if success:
                logger.debug(f"Successfully set window {hwnd} state to {state.name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error setting window {hwnd} state: {e}")
            return False
    
    def snap_to_edge(self,
                    hwnd: int,
                    edge: str,
                    monitor_handle: Optional[int] = None,
                    fill_height: bool = True) -> bool:
        """
        Snap window to screen edge (left, right, top, bottom).
        
        Args:
            hwnd: Window handle
            edge: Edge to snap to ('left', 'right', 'top', 'bottom')
            monitor_handle: Target monitor (None for current)
            fill_height: Whether to fill screen height for left/right snap
            
        Returns:
            True if successful
        """
        try:
            current_rect = self.api.get_window_rect(hwnd)
            if not current_rect:
                return False
            
            # Get target monitor
            if monitor_handle is None:
                monitor = self._get_monitor_from_window(hwnd)
            else:
                monitor = self._monitors.get(monitor_handle)
            
            if not monitor:
                return False
            
            work_area = monitor.work_rect
            
            # Calculate snap position
            if edge == 'left':
                x = work_area.left
                y = work_area.top if fill_height else current_rect.top
                width = work_area.width // 2
                height = work_area.height if fill_height else current_rect.height
            elif edge == 'right':
                x = work_area.left + work_area.width // 2
                y = work_area.top if fill_height else current_rect.top
                width = work_area.width // 2
                height = work_area.height if fill_height else current_rect.height
            elif edge == 'top':
                x = current_rect.left
                y = work_area.top
                width = current_rect.width
                height = work_area.height // 2
            elif edge == 'bottom':
                x = current_rect.left
                y = work_area.top + work_area.height // 2
                width = current_rect.width
                height = work_area.height // 2
            else:
                return False
            
            return self.move_window(hwnd, x, y, width, height)
            
        except Exception as e:
            logger.error(f"Error snapping window {hwnd} to {edge}: {e}")
            return False
    
    def arrange_windows_grid(self,
                           window_handles: List[int],
                           rows: int,
                           cols: int,
                           monitor_handle: Optional[int] = None,
                           padding: int = 5) -> bool:
        """
        Arrange multiple windows in a grid layout.
        
        Args:
            window_handles: List of window handles to arrange
            rows: Number of rows in grid
            cols: Number of columns in grid
            monitor_handle: Target monitor (None for primary)
            padding: Padding between windows
            
        Returns:
            True if all windows arranged successfully
        """
        try:
            if not window_handles or rows <= 0 or cols <= 0:
                return False
            
            # Get target monitor
            if monitor_handle is None:
                monitor = self._get_primary_monitor()
            else:
                monitor = self._monitors.get(monitor_handle)
            
            if not monitor:
                return False
            
            work_area = monitor.work_rect
            
            # Calculate cell dimensions
            cell_width = (work_area.width - padding * (cols + 1)) // cols
            cell_height = (work_area.height - padding * (rows + 1)) // rows
            
            success_count = 0
            
            for i, hwnd in enumerate(window_handles[:rows * cols]):
                row = i // cols
                col = i % cols
                
                x = work_area.left + padding + col * (cell_width + padding)
                y = work_area.top + padding + row * (cell_height + padding)
                
                if self.move_window(hwnd, x, y, cell_width, cell_height):
                    success_count += 1
            
            return success_count == len(window_handles[:rows * cols])
            
        except Exception as e:
            logger.error(f"Error arranging windows in grid: {e}")
            return False
    
    def rollback_last_operation(self) -> bool:
        """
        Rollback the last window operation.
        
        Returns:
            True if rollback successful
        """
        with self._lock:
            if not self._operation_history:
                return False
            
            try:
                operation = self._operation_history[-1]
                
                # Restore original position
                if operation.operation_type in ["move_window", "resize_window"]:
                    success = self.api.move_window(
                        operation.hwnd,
                        operation.original_rect.left,
                        operation.original_rect.top,
                        operation.original_rect.width,
                        operation.original_rect.height,
                        True
                    )
                elif operation.operation_type == "set_window_state":
                    success = self.set_window_state(operation.hwnd, operation.original_state)
                else:
                    success = False
                
                if success:
                    self._operation_history.pop()
                    logger.debug(f"Successfully rolled back operation on window {operation.hwnd}")
                
                return success
                
            except Exception as e:
                logger.error(f"Error rolling back operation: {e}")
                return False
    
    def get_monitor_info(self, refresh: bool = False) -> Dict[int, MonitorInfo]:
        """
        Get information about all monitors.
        
        Args:
            refresh: Whether to refresh monitor information
            
        Returns:
            Dictionary mapping monitor handles to monitor info
        """
        if refresh:
            self._update_monitor_info()
        return self._monitors.copy()
    
    def get_window_constraints_info(self, hwnd: int) -> Dict[str, any]:
        """
        Get information about window constraints and capabilities.
        
        Args:
            hwnd: Window handle
            
        Returns:
            Dictionary with constraint information
        """
        try:
            current_rect = self.api.get_window_rect(hwnd)
            current_state = self._get_window_state(hwnd)
            monitor = self._get_monitor_from_window(hwnd)
            
            return {
                'current_rect': current_rect,
                'current_state': current_state,
                'monitor': monitor,
                'can_move': self._can_move_window(hwnd),
                'can_resize': self._can_resize_window(hwnd),
                'is_topmost': self._is_window_topmost(hwnd),
                'dpi_aware': self._is_dpi_aware(hwnd)
            }
            
        except Exception as e:
            logger.error(f"Error getting window constraints info: {e}")
            return {}
    
    def _update_monitor_info(self):
        """Update information about all monitors."""
        self._monitors.clear()
        
        def monitor_enum_proc(hmonitor, hdc, rect_ptr, data):
            try:
                # Define MONITORINFO structure
                class MONITORINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", wintypes.DWORD),
                        ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT),
                        ("dwFlags", wintypes.DWORD)
                    ]
                
                # Get monitor info
                monitor_info = MONITORINFO()
                monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
                success = windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(monitor_info))
                
                if not success:
                    return True
                
                # Create monitor info object
                monitor_rect = WindowRect(
                    monitor_info.rcMonitor.left, monitor_info.rcMonitor.top,
                    monitor_info.rcMonitor.right, monitor_info.rcMonitor.bottom
                )
                
                # Create work area rect
                work_rect = WindowRect(
                    monitor_info.rcWork.left, monitor_info.rcWork.top,
                    monitor_info.rcWork.right, monitor_info.rcWork.bottom
                )
                
                # Get DPI information
                dpi_x, dpi_y = self._get_monitor_dpi(hmonitor)
                
                self._monitors[hmonitor] = MonitorInfo(
                    handle=hmonitor,
                    rect=monitor_rect,
                    work_rect=work_rect,
                    is_primary=bool(monitor_info.dwFlags & 1),  # MONITORINFOF_PRIMARY
                    device_name=f"Monitor_{hmonitor}",
                    dpi_x=dpi_x,
                    dpi_y=dpi_y,
                    scale_factor=dpi_x / 96.0
                )
                
            except Exception as e:
                logger.debug(f"Error processing monitor {hmonitor}: {e}")
            
            return True
        
        try:
            # Enumerate all monitors
            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.c_bool,
                wintypes.HMONITOR,
                wintypes.HDC, 
                ctypes.POINTER(wintypes.RECT),
                wintypes.LPARAM
            )
            
            windll.user32.EnumDisplayMonitors(
                None, None, MONITORENUMPROC(monitor_enum_proc), 0
            )
            
            logger.debug(f"Updated info for {len(self._monitors)} monitors")
            
        except Exception as e:
            logger.error(f"Error updating monitor info: {e}")
    
    def _apply_constraints(self,
                          x: int, y: int, width: int, height: int,
                          constraints: WindowConstraints) -> Tuple[int, int, int, int]:
        """Apply constraints to window position and size."""
        # Apply size constraints
        width = max(width, constraints.min_width)
        height = max(height, constraints.min_height)
        
        if constraints.max_width:
            width = min(width, constraints.max_width)
        if constraints.max_height:
            height = min(height, constraints.max_height)
        
        # Apply aspect ratio if required
        if constraints.maintain_aspect_ratio and constraints.aspect_ratio:
            current_ratio = width / height
            if abs(current_ratio - constraints.aspect_ratio) > 0.01:
                # Adjust height to maintain aspect ratio
                height = int(width / constraints.aspect_ratio)
        
        # Apply screen constraints
        if constraints.keep_on_screen:
            x, y = self._constrain_to_screen(x, y, width, height, constraints.respect_work_area)
        
        return x, y, width, height
    
    def _constrain_to_screen(self, x: int, y: int, width: int, height: int, work_area: bool) -> Tuple[int, int]:
        """Constrain window position to stay on screen."""
        # For now, use primary monitor
        monitor = self._get_primary_monitor()
        if not monitor:
            return x, y
        
        bounds = monitor.work_rect if work_area else monitor.rect
        
        # Ensure window doesn't go off screen
        x = max(bounds.left, min(x, bounds.left + bounds.width - width))
        y = max(bounds.top, min(y, bounds.top + bounds.height - height))
        
        return x, y
    
    def _get_window_state(self, hwnd: int) -> WindowState:
        """Get current window state."""
        try:
            placement = wintypes.WINDOWPLACEMENT()
            placement.length = ctypes.sizeof(placement)
            
            if windll.user32.GetWindowPlacement(hwnd, ctypes.byref(placement)):
                show_state = placement.showCmd
                if show_state == 2:
                    return WindowState.MINIMIZED
                elif show_state == 3:
                    return WindowState.MAXIMIZED
                else:
                    return WindowState.NORMAL
            
        except Exception:
            pass
        
        return WindowState.NORMAL
    
    def _get_primary_monitor(self) -> Optional[MonitorInfo]:
        """Get primary monitor information."""
        for monitor in self._monitors.values():
            if monitor.is_primary:
                return monitor
        
        # Fallback to first monitor
        return next(iter(self._monitors.values())) if self._monitors else None
    
    def _get_monitor_from_window(self, hwnd: int) -> Optional[MonitorInfo]:
        """Get monitor containing the specified window."""
        try:
            hmonitor = windll.user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
            return self._monitors.get(hmonitor)
        except Exception:
            return self._get_primary_monitor()
    
    def _get_monitor_dpi(self, hmonitor: int) -> Tuple[int, int]:
        """Get DPI for a specific monitor."""
        try:
            dpi_x = ctypes.c_uint()
            dpi_y = ctypes.c_uint() 
            
            # Try to get DPI (Windows 8.1+)
            result = windll.shcore.GetDpiForMonitor(
                hmonitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)
            )
            
            if result == 0:
                return dpi_x.value, dpi_y.value
                
        except Exception:
            pass
        
        # Fallback to system DPI
        return 96, 96
    
    def _scale_coordinates_to_physical(self, x: int, y: int) -> Tuple[int, int]:
        """Scale logical coordinates to physical coordinates."""
        # For now, return as-is (would implement DPI scaling here)
        return x, y
    
    def _scale_size_to_physical(self, width: int, height: int) -> Tuple[int, int]:
        """Scale logical size to physical size."""
        # For now, return as-is (would implement DPI scaling here)
        return width, height
    
    def _animate_window_move(self, hwnd: int, start_rect: WindowRect, end_rect: WindowRect) -> bool:
        """Animate window movement between positions."""
        try:
            steps = 10
            duration = 0.2  # 200ms
            step_time = duration / steps
            
            for i in range(steps + 1):
                progress = i / steps
                
                # Interpolate position
                current_x = int(start_rect.left + (end_rect.left - start_rect.left) * progress)
                current_y = int(start_rect.top + (end_rect.top - start_rect.top) * progress)
                current_width = int(start_rect.width + (end_rect.width - start_rect.width) * progress)
                current_height = int(start_rect.height + (end_rect.height - start_rect.height) * progress)
                
                success = self.api.move_window(hwnd, current_x, current_y, current_width, current_height, True)
                if not success:
                    return False
                
                if i < steps:
                    time.sleep(step_time)
            
            return True
            
        except Exception as e:
            logger.error(f"Error animating window movement: {e}")
            return False
    
    def _can_move_window(self, hwnd: int) -> bool:
        """Check if window can be moved."""
        try:
            style = windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            return not (style & 0x00000080)  # WS_EX_TOOLWINDOW
        except Exception:
            return True
    
    def _can_resize_window(self, hwnd: int) -> bool:
        """Check if window can be resized.""" 
        try:
            style = windll.user32.GetWindowLongW(hwnd, -16)  # GWL_STYLE
            return bool(style & 0x00040000)  # WS_THICKFRAME
        except Exception:
            return True
    
    def _is_window_topmost(self, hwnd: int) -> bool:
        """Check if window is topmost."""
        try:
            ex_style = windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            return bool(ex_style & 0x00000008)  # WS_EX_TOPMOST
        except Exception:
            return False
    
    def _is_dpi_aware(self, hwnd: int) -> bool:
        """Check if window is DPI aware."""
        # Simplified check - would implement full DPI awareness detection
        return True
    
    def _add_operation_to_history(self, operation: WindowOperation):
        """Add operation to history for rollback."""
        self._operation_history.append(operation)
        
        # Limit history size
        if len(self._operation_history) > self._max_history:
            self._operation_history.pop(0)
    
    def detect_game_engine(self, hwnd: int) -> GameEngineInfo:
        """
        Detect game engine type and characteristics.
        
        Args:
            hwnd: Window handle
            
        Returns:
            GameEngineInfo: Information about the detected engine
        """
        try:
            # Get window information
            title_buffer = ctypes.create_unicode_buffer(512)
            title_length = windll.user32.GetWindowTextW(hwnd, title_buffer, 512)
            window_title = title_buffer.value if title_length > 0 else ""
            
            style = windll.user32.GetWindowLongW(hwnd, -16)  # GWL_STYLE
            ex_style = windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            
            # Get process information for more context
            process_id = wintypes.DWORD()
            windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            
            # Detect engine based on window title and characteristics
            engine_type = "unknown"
            confidence = 0.0
            
            title_lower = window_title.lower() if window_title else ""
            
            # Unity detection
            if any(pattern.lower() in title_lower for pattern in GAME_ENGINE_PATTERNS['unity']):
                engine_type = "unity"
                confidence = 0.9
            # Unreal detection
            elif any(pattern.lower() in title_lower for pattern in GAME_ENGINE_PATTERNS['unreal']):
                engine_type = "unreal"
                confidence = 0.9
            # DirectX/D3D detection
            elif any(pattern.lower() in title_lower for pattern in GAME_ENGINE_PATTERNS['directx']):
                engine_type = "directx"
                confidence = 0.7
            # Check for popup windows (common in older games)
            elif style & WS_POPUP:
                engine_type = "legacy_popup"
                confidence = 0.6
            # Check for borderless windows
            elif not (style & WS_CAPTION) and (style & WS_VISIBLE):
                engine_type = "borderless"
                confidence = 0.5
            else:
                engine_type = "standard"
                confidence = 0.3
            
            # Determine special handling requirements
            requires_special = self._requires_special_handling(style, ex_style, engine_type)
            supports_resize = self._supports_resize(style, engine_type)
            supports_move = self._supports_move(style, engine_type)
            
            return GameEngineInfo(
                engine_type=engine_type,
                confidence=confidence,
                window_style=style,
                extended_style=ex_style,
                requires_special_handling=requires_special,
                supports_resize=supports_resize,
                supports_move=supports_move
            )
            
        except Exception as e:
            logger.error(f"Error detecting game engine for window {hwnd}: {e}")
            return GameEngineInfo(
                engine_type="unknown",
                confidence=0.0,
                window_style=0,
                extended_style=0
            )
    
    def _requires_special_handling(self, style: int, ex_style: int, engine_type: str) -> bool:
        """Determine if window requires special handling."""
        # Popup windows often need style conversion
        if style & WS_POPUP:
            return True
        
        # Unity games sometimes need special handling
        if engine_type == "unity":
            return True
            
        # Legacy games with specific styles
        if engine_type == "legacy_popup":
            return True
            
        return False
    
    def _supports_resize(self, style: int, engine_type: str) -> bool:
        """Check if window supports resizing."""
        # Check for thick frame (resizable border)
        if not (style & WS_THICKFRAME):
            return False
            
        # Some game engines don't handle resize properly
        if engine_type in ["legacy_popup"]:
            return False
            
        return True
    
    def _supports_move(self, style: int, engine_type: str) -> bool:
        """Check if window supports moving."""
        # Most windows can be moved unless they're child windows
        if style & WS_CHILD:
            return False
            
        return True
    
    def move_window_enhanced(self, hwnd: int, x: int, y: int, width: int, height: int, 
                           constraints: WindowConstraints = None) -> bool:
        """
        Enhanced window moving with game engine specific handling.
        
        Args:
            hwnd: Window handle
            x, y: New position
            width, height: New size
            constraints: Optional constraints
            
        Returns:
            bool: Success status
        """
        try:
            # Detect game engine first
            engine_info = self.detect_game_engine(hwnd)
            logger.info(f"Detected engine: {engine_info.engine_type} (confidence: {engine_info.confidence})")
            
            # Store original state for rollback
            original_rect = self.api.get_window_rect(hwnd)
            original_state = self._get_window_state(hwnd)
            operation = WindowOperation(
                hwnd=hwnd,
                operation_type="move_enhanced", 
                original_rect=original_rect,
                original_state=original_state
            )
            
            success = False
            
            if engine_info.requires_special_handling:
                success = self._move_window_special(hwnd, x, y, width, height, engine_info)
            else:
                success = self._move_window_standard(hwnd, x, y, width, height)
            
            if success:
                self._add_operation_to_history(operation)
                logger.info(f"Successfully moved window {hwnd} using {engine_info.engine_type} handling")
            else:
                logger.warning(f"Failed to move window {hwnd} with {engine_info.engine_type} handling")
            
            return success
            
        except Exception as e:
            logger.error(f"Error in enhanced window move: {e}")
            return False
    
    def _move_window_special(self, hwnd: int, x: int, y: int, width: int, height: int, 
                           engine_info: GameEngineInfo) -> bool:
        """Handle special cases for stubborn games."""
        try:
            if engine_info.engine_type == "legacy_popup":
                return self._handle_popup_window(hwnd, x, y, width, height)
            elif engine_info.engine_type == "unity":
                return self._handle_unity_window(hwnd, x, y, width, height)
            elif engine_info.engine_type == "borderless":
                return self._handle_borderless_window(hwnd, x, y, width, height)
            else:
                # Fallback to standard handling
                return self._move_window_standard(hwnd, x, y, width, height)
                
        except Exception as e:
            logger.error(f"Error in special window handling: {e}")
            return False
    
    def _handle_popup_window(self, hwnd: int, x: int, y: int, width: int, height: int) -> bool:
        """Handle popup windows by converting to overlapped window style."""
        try:
            # Get current style
            current_style = windll.user32.GetWindowLongW(hwnd, -16)  # GWL_STYLE
            
            # Convert popup to overlapped window
            new_style = (current_style & ~WS_POPUP) | WS_OVERLAPPEDWINDOW
            
            # Set new style
            windll.user32.SetWindowLongW(hwnd, -16, new_style)
            
            # Apply frame changes
            windll.user32.SetWindowPos(
                hwnd, 0, x, y, width, height,
                WindowPosition.FRAMECHANGED | WindowPosition.SHOWWINDOW
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling popup window: {e}")
            return False
    
    def _handle_unity_window(self, hwnd: int, x: int, y: int, width: int, height: int) -> bool:
        """Handle Unity game windows."""
        try:
            # Unity games often respond better to multiple step approach
            # First, make sure window is visible and active
            windll.user32.ShowWindow(hwnd, 1)  # SW_SHOWNORMAL
            windll.user32.SetForegroundWindow(hwnd)
            
            # Small delay to let Unity process the changes
            time.sleep(0.1)
            
            # Then move and resize
            success = windll.user32.MoveWindow(hwnd, x, y, width, height, True)
            
            # Additional attempt with SetWindowPos if MoveWindow failed
            if not success:
                success = windll.user32.SetWindowPos(
                    hwnd, 0, x, y, width, height,
                    WindowPosition.SHOWWINDOW | WindowPosition.FRAMECHANGED
                )
            
            return bool(success)
            
        except Exception as e:
            logger.error(f"Error handling Unity window: {e}")
            return False
    
    def _handle_borderless_window(self, hwnd: int, x: int, y: int, width: int, height: int) -> bool:
        """Handle borderless fullscreen windows."""
        try:
            # For borderless windows, we might need to add a border first
            current_style = windll.user32.GetWindowLongW(hwnd, -16)  # GWL_STYLE
            
            # Add caption and border if not present
            if not (current_style & WS_CAPTION):
                new_style = current_style | WS_CAPTION | WS_BORDER
                windll.user32.SetWindowLongW(hwnd, -16, new_style)
                
                # Apply changes
                windll.user32.SetWindowPos(
                    hwnd, 0, 0, 0, 0, 0,
                    WindowPosition.NOMOVE | WindowPosition.NOSIZE | WindowPosition.FRAMECHANGED
                )
            
            # Now move and resize
            return bool(windll.user32.MoveWindow(hwnd, x, y, width, height, True))
            
        except Exception as e:
            logger.error(f"Error handling borderless window: {e}")
            return False
    
    def _move_window_standard(self, hwnd: int, x: int, y: int, width: int, height: int) -> bool:
        """Standard window moving approach."""
        try:
            return bool(windll.user32.MoveWindow(hwnd, x, y, width, height, True))
        except Exception as e:
            logger.error(f"Error in standard window move: {e}")
            return False

# Default instance
default_manipulator = WindowManipulator()

# Convenience functions
def move_window(hwnd: int, x: int, y: int, width: int = None, height: int = None, 
               constraints: WindowConstraints = None) -> bool:
    """Move window using default manipulator."""
    return default_manipulator.move_window(hwnd, x, y, width, height, constraints)

def center_window(hwnd: int, monitor_handle: int = None) -> bool:
    """Center window using default manipulator."""
    return default_manipulator.center_window(hwnd, monitor_handle)

def snap_to_edge(hwnd: int, edge: str, monitor_handle: int = None) -> bool:
    """Snap window to edge using default manipulator."""
    return default_manipulator.snap_to_edge(hwnd, edge, monitor_handle)