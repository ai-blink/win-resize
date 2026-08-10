"""
Profile Management System
========================

Comprehensive profile management system for saving, loading, and managing
window configurations with persistent storage and automatic matching.

Key Features:
- Profile data model with JSON serialization
- Persistent storage with file-based backend
- Profile matching by window title/process name
- CRUD operations for profile management
- Auto-apply functionality
- Profile validation and migration
- Advanced features: size locking, mouse constraint
"""

import json
import os
import shutil
import time
import re
import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import hashlib

from .windows_api import WindowRect
from .advanced_features_fixed import get_advanced_features

logger = logging.getLogger(__name__)

class MatchingStrategy(Enum):
    """Strategies for matching profiles to windows."""
    EXACT_TITLE = "exact_title"          # Exact window title match
    TITLE_CONTAINS = "title_contains"    # Window title contains pattern
    TITLE_REGEX = "title_regex"          # Regex pattern match on title
    PROCESS_NAME = "process_name"        # Match by process name
    EXECUTABLE_PATH = "executable_path"  # Match by full executable path
    COMBINED = "combined"                # Multiple criteria
    SMART = "smart"                      # AI-enhanced matching

class ProfileType(Enum):
    """Types of profiles for different use cases."""
    WINDOW_CONFIG = "window_config"      # Single window configuration
    LAYOUT = "layout"                    # Multiple window layout
    APPLICATION = "application"          # Application-specific profile
    WORKSPACE = "workspace"              # Complete workspace setup

@dataclass
class WindowConfiguration:
    """Configuration for a single window."""
    x: int
    y: int
    width: int
    height: int
    is_maximized: bool = False
    is_minimized: bool = False
    monitor_index: int = 0
    z_order: int = 0
    opacity: float = 0.0
    always_on_top: bool = False
    
    @classmethod
    def from_rect(cls, rect: WindowRect, **kwargs) -> 'WindowConfiguration':
        """Create configuration from WindowRect."""
        return cls(
            x=rect.left,
            y=rect.top, 
            width=rect.width,
            height=rect.height,
            **kwargs
        )
    
    def to_rect(self) -> WindowRect:
        """Convert to WindowRect."""
        return WindowRect(self.x, self.y, self.x + self.width, self.y + self.height)
    
    def validate(self) -> bool:
        """Validate configuration values."""
        return (
            self.width > 0 and 
            self.height > 0 and 
            0 <= self.opacity <= 1.0 and
            self.monitor_index >= 0
        )

@dataclass
class MatchingCriteria:
    """Criteria for matching profiles to windows."""
    strategy: MatchingStrategy
    window_title_pattern: Optional[str] = None
    process_name_pattern: Optional[str] = None
    window_class_pattern: Optional[str] = None
    executable_path_pattern: Optional[str] = None
    case_sensitive: bool = False
    regex_flags: int = 0
    priority: int = 50  # Higher = more priority
    # Auto-apply specific settings
    auto_apply_enabled: bool = False
    apply_delay: float = 2.0  # seconds to wait after window creation
    max_retries: int = 3
    retry_delay: float = 0.5
    only_on_startup: bool = False  # Only apply during system startup
    
    def matches_window(self, window_info: Dict[str, Any]) -> bool:
        """Check if criteria matches given window info."""
        try:
            if self.strategy == MatchingStrategy.EXACT_TITLE:
                return self._match_exact_title(window_info)
            elif self.strategy == MatchingStrategy.TITLE_CONTAINS:
                return self._match_title_contains(window_info)
            elif self.strategy == MatchingStrategy.TITLE_REGEX:
                return self._match_title_regex(window_info)
            elif self.strategy == MatchingStrategy.PROCESS_NAME:
                return self._match_process_name(window_info)
            elif self.strategy == MatchingStrategy.EXECUTABLE_PATH:
                return self._match_executable_path(window_info)
            elif self.strategy == MatchingStrategy.COMBINED:
                return self._match_combined(window_info)
            else:
                return False
        except Exception as e:
            logger.debug(f"Error matching window: {e}")
            return False
    
    def _match_exact_title(self, window_info: Dict[str, Any]) -> bool:
        """Match exact window title."""
        if not self.window_title_pattern:
            return False
        
        title = window_info.get('title', '')
        if self.case_sensitive:
            return title == self.window_title_pattern
        else:
            return title.lower() == self.window_title_pattern.lower()
    
    def _match_title_contains(self, window_info: Dict[str, Any]) -> bool:
        """Match title containing pattern."""
        if not self.window_title_pattern:
            return False
        
        title = window_info.get('title', '')
        pattern = self.window_title_pattern
        
        if not self.case_sensitive:
            title = title.lower()
            pattern = pattern.lower()
        
        return pattern in title
    
    def _match_title_regex(self, window_info: Dict[str, Any]) -> bool:
        """Match title with regex pattern."""
        if not self.window_title_pattern:
            return False
        
        title = window_info.get('title', '')
        flags = self.regex_flags
        if not self.case_sensitive:
            flags |= re.IGNORECASE
        
        try:
            return bool(re.search(self.window_title_pattern, title, flags))
        except re.error:
            logger.warning(f"Invalid regex pattern: {self.window_title_pattern}")
            return False
    
    def _match_process_name(self, window_info: Dict[str, Any]) -> bool:
        """Match by process name."""
        if not self.process_name_pattern:
            return False
        
        process_name = window_info.get('process_name', '')
        pattern = self.process_name_pattern
        
        if not self.case_sensitive:
            process_name = process_name.lower()
            pattern = pattern.lower()
        
        return pattern in process_name

    def _match_executable_path(self, window_info: Dict[str, Any]) -> bool:
        """Match the full executable path without relying on a temporary PID."""
        if not self.executable_path_pattern:
            return False

        executable_path = window_info.get('executable_path', '')
        if not executable_path:
            return False

        path = os.path.normpath(executable_path)
        pattern = os.path.normpath(self.executable_path_pattern)
        if not self.case_sensitive:
            path = os.path.normcase(path)
            pattern = os.path.normcase(pattern)

        return path == pattern
    
    def _match_combined(self, window_info: Dict[str, Any]) -> bool:
        """Match using multiple criteria (AND logic)."""
        has_criteria = False

        # Title check
        if self.window_title_pattern:
            has_criteria = True
            if not self._match_title_contains(window_info):
                return False
        
        # Process name check
        if self.process_name_pattern:
            has_criteria = True
            if not self._match_process_name(window_info):
                return False
        
        # Window class check
        if self.window_class_pattern:
            has_criteria = True
            window_class = window_info.get('class_name', '')
            pattern = self.window_class_pattern
            
            if not self.case_sensitive:
                window_class = window_class.lower()
                pattern = pattern.lower()
            
            if pattern not in window_class:
                return False

        if self.executable_path_pattern:
            has_criteria = True
            if not self._match_executable_path(window_info):
                return False

        return has_criteria

@dataclass
class Profile:
    """Window management profile with configuration and matching criteria."""
    name: str
    description: str = ""
    profile_type: ProfileType = ProfileType.WINDOW_CONFIG
    window_config: Optional[WindowConfiguration] = None
    matching_criteria: Optional[MatchingCriteria] = None
    tags: List[str] = field(default_factory=list)
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    applied_count: int = 0
    last_applied_at: Optional[float] = None
    version: str = "1.0"
    
    # Settings
    auto_apply: bool = False
    enabled: bool = True
    
    # Advanced features
    hotkey_enabled: bool = False
    hotkey_combination: str = ""
    hotkey_action: str = "apply_profile"  # apply_profile, toggle_window, minimize_restore
    
    # Size and position locking
    lock_size: bool = False
    lock_width: bool = False
    lock_height: bool = False
    lock_position: bool = False
    
    # Mouse constraint
    mouse_constraint: bool = False
    constraint_mode: str = "strict"  # strict, soft
    constraint_escape_key: str = "Escape"
    
    # Auto restore settings
    auto_restore: Optional[Dict] = None
    
    def __post_init__(self):
        """Post-initialization validation."""
        if not self.name.strip():
            raise ValueError("Profile name cannot be empty")
        
        # Generate ID based on name and creation time
        self.id = self._generate_id()
        
        # Initialize advanced feature tracking
        self._locked_windows = {}
        self._constrained_windows = set()
    
    def _generate_id(self) -> str:
        """Generate unique ID for profile."""
        content = f"{self.name}_{self.created_at}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def matches_window(self, window_info: Dict[str, Any]) -> bool:
        """Check if profile matches given window."""
        if not self.enabled or not self.matching_criteria:
            return False
        
        return self.matching_criteria.matches_window(window_info)
    
    def apply_to_window(self, window_info: Dict[str, Any]) -> bool:
        """Apply profile configuration to window."""
        if not self.window_config or not self.window_config.validate():
            logger.warning(f"Invalid window configuration in profile '{self.name}'")
            return False
        
        try:
            # Get window handle
            hwnd = window_info.get('hwnd')
            if not hwnd:
                logger.error("No window handle provided")
                return False
            
            # Validate window handle exists and is valid before any operations
            try:
                import win32gui
                if not win32gui.IsWindow(hwnd):
                    logger.warning(f"Window handle {hwnd} is no longer valid - window may have been closed")
                    return False
            except Exception as e:
                logger.warning(f"Cannot validate window handle {hwnd}: {e}")
                return False
            
            # Import window manipulator for actual window operations
            from .enhanced_window_manipulator import EnhancedWindowManipulator
            manipulator = EnhancedWindowManipulator()
            
            # Log detailed window move attempt
            logger.info(f"🔄 프로필 '{self.name}' 적용 시도:")
            logger.info(f"   대상 창: {hwnd} ({window_info.get('title', 'Unknown')})")
            logger.info(f"   목표 위치: ({self.window_config.x}, {self.window_config.y})")
            logger.info(f"   목표 크기: {self.window_config.width}x{self.window_config.height}")

            # A maximized window ignores its saved normal-window geometry.
            # Restore it before moving unless the profile explicitly keeps it maximized.
            is_maximized = False
            if not self.window_config.is_maximized:
                try:
                    import win32con
                    placement = win32gui.GetWindowPlacement(hwnd)
                    is_maximized = placement[1] == win32con.SW_SHOWMAXIMIZED
                except Exception as state_error:
                    logger.warning(f"Could not determine maximized state for window {hwnd}: {state_error}")

            if is_maximized:
                restore_result = manipulator.enhanced_restore_window(hwnd)
                restore_success = getattr(restore_result, 'success', bool(restore_result))
                if not restore_success:
                    logger.error(f"Failed to restore maximized window {hwnd} before applying geometry")
                    return False
            
            # Apply window configuration
            result = manipulator.enhanced_move_window(
                hwnd,
                self.window_config.x,
                self.window_config.y,
                self.window_config.width,
                self.window_config.height
            )
            
            # Handle both new result object and legacy boolean return
            if hasattr(result, 'success'):
                success = result.success
                error_info = getattr(result, 'error_info', 'Unknown error')
                logger.info(f"   Enhanced manipulator 결과: success={success}, error={error_info}")
            else:
                # Legacy return - assume boolean or int
                success = bool(result)
                error_info = 'Legacy enhanced_move_window call'
                logger.info(f"   Enhanced manipulator 결과 (legacy): {result}")
            
            if not success:
                logger.error(f"❌ 창 설정 적용 실패: {error_info}")
                logger.info("📋 대안 방법으로 직접 Windows API 시도...")
                
                # Fallback to direct Windows API
                try:
                    import win32gui
                    
                    # Try MoveWindow directly
                    api_result = win32gui.MoveWindow(
                        hwnd,
                        self.window_config.x,
                        self.window_config.y,
                        self.window_config.width,
                        self.window_config.height,
                        True
                    )
                    
                    if api_result:
                        logger.info("✅ Windows API 직접 호출로 창 이동 성공")
                        success = True
                    else:
                        logger.error("❌ Windows API 직접 호출도 실패")
                        
                except Exception as api_e:
                    logger.error(f"❌ Windows API 직접 호출 중 오류: {api_e}")
                
                if not success:
                    return False
            
            # Apply window state if needed
            if self.window_config.is_maximized:
                manipulator.enhanced_maximize_window(hwnd)
            elif self.window_config.is_minimized:
                manipulator.enhanced_minimize_window(hwnd)
            
            # Apply always on top setting (both enable and disable)
            self._set_always_on_top(hwnd, self.window_config.always_on_top)
            
            # Apply advanced features
            advanced_success = self._apply_advanced_features(hwnd)
            
            # Update metadata
            self.applied_count += 1
            self.last_applied_at = time.time()
            self.modified_at = time.time()
            
            # Handle auto monitoring based on auto_apply setting
            if getattr(self, 'auto_apply', False):
                self._start_auto_monitoring(hwnd, window_info)
            else:
                # Stop monitoring if auto_apply is disabled
                self._stop_auto_monitoring(hwnd)
            
            if advanced_success:
                logger.info(f"Successfully applied profile '{self.name}' to window with advanced features")
            else:
                logger.warning(f"Applied profile '{self.name}' to window but some advanced features failed")
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying profile '{self.name}': {e}")
            return False
    
    def _set_always_on_top(self, hwnd, on_top: bool):
        """Set window to always on top with privilege handling."""
        try:
            import win32gui
            import win32con
            from .privilege_handler import check_window_permission, PermissionResult
            from .enhanced_window_manipulator import get_enhanced_window_manipulator
            
            # Check if we have permission to modify this window
            permission = check_window_permission(hwnd)
            
            if permission == PermissionResult.DENIED:
                logger.warning(f"Access denied for window {hwnd}. This window may require administrator privileges.")
                return False
            elif permission == PermissionResult.REQUIRES_ELEVATION:
                logger.warning(f"Window {hwnd} requires elevated privileges. Please run as administrator for full functionality.")
                return False
            
            # Try to use enhanced manipulator first (with privilege handling)
            try:
                manipulator = get_enhanced_window_manipulator()
                if on_top:
                    success = manipulator.set_window_always_on_top(hwnd, True)
                else:
                    success = manipulator.set_window_always_on_top(hwnd, False)
                
                if success:
                    action = "Set" if on_top else "Removed"
                    logger.info(f"{action} always on top for window {hwnd}")
                    return True
                    
            except Exception as enhanced_error:
                logger.debug(f"Enhanced manipulator failed: {enhanced_error}, trying direct API")
            
            # Fallback to direct API call
            if on_top:
                win32gui.SetWindowPos(
                    hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                )
                logger.info(f"Set window {hwnd} to always on top")
            else:
                win32gui.SetWindowPos(
                    hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                )
                logger.info(f"Removed always on top from window {hwnd}")
                
            return True
                
        except Exception as e:
            error_code = getattr(e, 'winerror', None)
            if error_code == 5:  # Access Denied
                logger.warning(f"권한이 부족합니다. 일부 창은 관리자 권한이 필요할 수 있습니다. (창 ID: {hwnd})")
            else:
                logger.error(f"Error setting always on top: {e}")
            return False
    
    def _start_auto_monitoring(self, hwnd, window_info):
        """Start automatic monitoring for auto_apply profiles."""
        try:
            from .enhanced_window_monitor import get_enhanced_monitor, WindowMonitorConfig, MonitoringMethod
            
            logger.info(f"Starting auto monitoring for profile '{self.name}' on window {hwnd}")
            
            # Get enhanced monitor
            monitor = get_enhanced_monitor()
            
            # Get window title
            window_title = window_info.get('title', 'Unknown Window')
            
            # Create monitoring configuration
            config = WindowMonitorConfig(
                hwnd=hwnd,
                window_title=window_title,
                target_rect=(
                    self.window_config.x,
                    self.window_config.y,
                    self.window_config.x + self.window_config.width,
                    self.window_config.y + self.window_config.height
                ),
                method=MonitoringMethod.HYBRID,
                polling_interval=2.0,
                pause_when_inactive=False,  # Important: Never pause
                auto_restore=True,
                restore_on_focus=True,
                restore_on_resize=True,
                restore_on_move=True,
                tolerance=5,
                max_restore_attempts=-1,  # Unlimited attempts
                is_game_window='StarCraft' in window_title or 'Brood War' in window_title
            )
            
            # Apply auto_restore settings if available
            if hasattr(self, 'auto_restore') and isinstance(self.auto_restore, dict):
                auto_restore = self.auto_restore
                config.polling_interval = auto_restore.get('polling_interval', 2.0)
                config.tolerance = auto_restore.get('tolerance', 5)
                config.restore_on_focus = auto_restore.get('restore_on_focus', True)
                config.restore_on_resize = auto_restore.get('restore_on_resize', True)
                config.restore_on_move = auto_restore.get('restore_on_move', True)
                config.pause_when_inactive = auto_restore.get('pause_when_inactive', False)
                max_attempts = auto_restore.get('max_attempts', 50)
                config.max_restore_attempts = max_attempts if max_attempts > 0 else -1
                
                logger.info(f"Applied custom auto_restore settings: {auto_restore}")
            
            # Add window to monitor
            success = monitor.add_window(hwnd, config)
            
            if success:
                logger.info(f"✅ Auto monitoring started for '{self.name}' on window {hwnd}")
            else:
                logger.warning(f"❌ Failed to start auto monitoring for '{self.name}' on window {hwnd}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error starting auto monitoring: {e}")
            return False
    
    def _stop_auto_monitoring(self, hwnd: int) -> bool:
        """Stop auto monitoring for a window."""
        try:
            from .enhanced_window_monitor import get_enhanced_monitor
            monitor = get_enhanced_monitor()
            
            success = monitor.remove_window(hwnd)
            
            if success:
                logger.info(f"✅ Auto monitoring stopped for '{self.name}' on window {hwnd}")
            else:
                logger.warning(f"❌ Failed to stop auto monitoring for '{self.name}' on window {hwnd}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error stopping auto monitoring: {e}")
            return False
    
    def _apply_advanced_features(self, hwnd):
        """Apply advanced features to the window."""
        success = True
        try:
            # Initialize tracking attributes if they don't exist (for loaded profiles)
            if not hasattr(self, '_locked_windows'):
                self._locked_windows = {}
            if not hasattr(self, '_constrained_windows'):
                self._constrained_windows = set()
            
            logger.info(f"Applying advanced features to window {hwnd}:")
            logger.info(f"  - Mouse constraint: {self.mouse_constraint}")
            logger.info(f"  - Lock size: {self.lock_size}")
            logger.info(f"  - Lock width: {self.lock_width}")
            logger.info(f"  - Lock height: {self.lock_height}")
            logger.info(f"  - Lock position: {self.lock_position}")
            
            # Apply size/position locking FIRST (may interfere with mouse constraint)
            has_window_lock = (
                self.lock_size or self.lock_width or self.lock_height or self.lock_position
            )
            if has_window_lock:
                logger.info(f"Attempting to apply size/position lock...")
                lock_success = self._apply_size_position_lock(hwnd)
                if not lock_success:
                    success = False
                    logger.warning(f"Failed to apply size/position lock for window {hwnd}")
                else:
                    logger.info(f"Successfully applied size/position lock for window {hwnd}")
            else:
                # A profile with the lock disabled must release a previously active lock.
                # Without this, changing the setting cannot restore normal window movement.
                self.release_size_position_lock(hwnd)
            
            # Apply mouse constraint AFTER size lock (to prevent interference)
            if self.mouse_constraint:
                logger.info(f"Attempting to apply mouse constraint...")
                constraint_success = self._apply_mouse_constraint(hwnd)
                if not constraint_success:
                    success = False
                    logger.warning(f"Failed to apply mouse constraint for window {hwnd}")
                else:
                    logger.info(f"Successfully applied mouse constraint for window {hwnd}")
                    
                    # CRITICAL FIX: Ensure mouse constraint stays active after size lock
                    import time
                    time.sleep(0.5)  # Wait for size lock operations to complete
                    
                    # Verify constraint is still active and reapply if needed
                    logger.info(f"Verifying mouse constraint is still active...")
                    from core.alternative_mouse_constraint import get_alternative_constraint
                    alt_constraint = get_alternative_constraint()
                    constraint_info = alt_constraint.get_constraint_info()
                    
                    if not constraint_info['active'] or constraint_info['window'] != hwnd:
                        logger.warning(f"Mouse constraint was deactivated! Reapplying...")
                        reapply_success = self._apply_mouse_constraint(hwnd)
                        if reapply_success:
                            logger.info(f"Successfully reapplied mouse constraint after size lock interference")
                        else:
                            logger.error(f"Failed to reapply mouse constraint after size lock interference")
                            success = False
                    else:
                        logger.info(f"Mouse constraint verification passed: active={constraint_info['active']}, window={constraint_info['window']}")
            else:
                self.release_mouse_constraint(hwnd)
            
            # Apply opacity/transparency (0% = 완전불투명, 1-100% = 투명)
            if hasattr(self.window_config, 'opacity') and self.window_config.opacity >= 0.0:
                logger.info(f"Attempting to apply opacity: {self.window_config.opacity*100:.0f}%")
                # Simple opacity application using Windows API
                try:
                    import win32gui, win32con
                    alpha = int(255 * (1.0 - self.window_config.opacity))
                    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                    if not (ex_style & win32con.WS_EX_LAYERED):
                        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style | win32con.WS_EX_LAYERED)
                    opacity_success = win32gui.SetLayeredWindowAttributes(hwnd, 0, alpha, win32con.LWA_ALPHA)
                except:
                    opacity_success = False
                if not opacity_success:
                    success = False
                    logger.warning(f"Failed to apply opacity for window {hwnd}")
                else:
                    logger.info(f"Successfully applied opacity {self.window_config.opacity*100:.0f}% to window {hwnd}")
            
            return success
        except Exception as e:
            logger.error(f"Error applying advanced features: {e}")
            return False
    
    def _apply_opacity(self, hwnd: int, opacity: float) -> bool:
        """Apply opacity/transparency to window using multiple fallback methods."""
        try:
            import win32gui
            import win32con
            
            logger.info(f"Applying opacity {opacity*100:.0f}% to window {hwnd}")
            
            if not win32gui.IsWindow(hwnd):
                logger.error(f"Invalid window handle: {hwnd}")
                return False
            
            # Convert opacity (0.0=opaque, 1.0=transparent) to Windows alpha (255=opaque, 0=transparent)
            alpha = int(255 * (1.0 - opacity))
            
            # Method 1: Standard Windows transparency
            try:
                # Make window layered
                ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                if not (ex_style & win32con.WS_EX_LAYERED):
                    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style | win32con.WS_EX_LAYERED)
                
                # Apply transparency
                success = win32gui.SetLayeredWindowAttributes(hwnd, 0, alpha, win32con.LWA_ALPHA)
                if success:
                    logger.info(f"Applied opacity {opacity*100:.0f}% successfully")
                    return True
            except Exception as e:
                logger.warning(f"Standard method failed: {e}")
            
            # Method 2: Alternative API approach
            try:
                import win32api
                current_style = win32api.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                win32api.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, current_style | win32con.WS_EX_LAYERED)
                success = win32api.SetLayeredWindowAttributes(hwnd, 0, alpha, win32con.LWA_ALPHA)
                if success:
                    logger.info(f"Applied opacity {opacity*100:.0f}% using alternative method")
                    return True
            except Exception as e:
                logger.warning(f"Alternative method failed: {e}")
            
            logger.error(f"All opacity methods failed for window {hwnd}")
            return False
            
        except Exception as e:
            logger.error(f"Fatal error applying opacity: {e}")
            return False
    
    def _apply_mouse_constraint(self, hwnd):
        """Apply mouse constraint using improved implementation."""
        try:
            logger.info(f"Applying mouse constraint to window {hwnd} (mode: {self.constraint_mode})")
            
            # Use improved advanced features implementation
            advanced_features = get_advanced_features()
            result = advanced_features.apply_mouse_constraint(hwnd, self.constraint_mode)
            
            if result:
                logger.info(f"Successfully applied mouse constraint to window {hwnd}")
                return True
            else:
                logger.warning(f"Failed to apply mouse constraint to window {hwnd}")
                return False
                
        except Exception as e:
            logger.error(f"Error applying mouse constraint: {e}")
            return False
    
    def release_mouse_constraint(self, hwnd=None):
        """Release mouse constraint using improved implementation."""
        try:
            logger.info(f"Releasing mouse constraint for window {hwnd if hwnd else 'all windows'}")
            
            # Use improved advanced features implementation
            advanced_features = get_advanced_features()
            result = advanced_features.release_mouse_constraint(hwnd)
            
            if result:
                logger.info(f"Successfully released mouse constraint")
                return True
            else:
                logger.warning(f"Failed to release mouse constraint")
                return False
                
        except Exception as e:
            logger.error(f"Error releasing mouse constraint: {e}")
            return False
    
    def _apply_size_position_lock(self, hwnd):
        """Apply size and position locking using improved implementation."""
        try:
            import win32gui
            
            # Validate window exists
            if not win32gui.IsWindow(hwnd):
                logger.error(f"Invalid window handle for size/position lock: {hwnd}")
                return False
            
            logger.info(f"Applying size/position lock to window {hwnd}")
            logger.info(f"  - Lock size: {self.lock_size}")
            logger.info(f"  - Lock width: {self.lock_width}")
            logger.info(f"  - Lock height: {self.lock_height}")
            logger.info(f"  - Lock position: {self.lock_position}")
            
            # Get current window rect to use as target
            current_rect = win32gui.GetWindowRect(hwnd)
            
            # Prepare lock configuration
            lock_config = {
                'lock_size': self.lock_size,
                'lock_width': self.lock_width,
                'lock_height': self.lock_height,
                'lock_position': self.lock_position,
                'target_rect': current_rect
            }
            
            # 향상된 자동 복구 설정 준비
            enhanced_config = None
            if hasattr(self, 'auto_restore') and isinstance(self.auto_restore, dict):
                enhanced_config = self.auto_restore
                logger.info(f"향상된 자동 복구 설정 적용: {enhanced_config}")
            
            # Use improved advanced features implementation
            advanced_features = get_advanced_features()
            result = advanced_features.apply_size_position_lock(hwnd, lock_config, enhanced_config)
            
            if result:
                logger.info(f"Successfully applied size/position lock to window {hwnd}")
                return True
            else:
                logger.warning(f"Failed to apply size/position lock to window {hwnd}")
                return False
                
        except Exception as e:
            logger.error(f"Error applying size/position lock: {e}")
            return False
    
    def _monitor_locked_window(self, hwnd, locked_config):
        """Legacy method - monitoring is now handled by advanced_features_fixed.py"""
        logger.info(f"Legacy monitoring method called - advanced features implementation handles this")
        pass
    
    def release_size_position_lock(self, hwnd=None):
        """Release size/position lock using improved implementation."""
        try:
            logger.info(f"Releasing size/position lock for window {hwnd if hwnd else 'all windows'}")
            
            # Use improved advanced features implementation
            advanced_features = get_advanced_features()
            advanced_features.stop_monitoring(hwnd)
            
            logger.info(f"Successfully released size/position lock")
            return True
                
        except Exception as e:
            logger.error(f"Error releasing size/position lock: {e}")
            return False
    
    def update_from_window(self, window_info: Dict[str, Any]):
        """Update profile configuration from current window state."""
        if 'rect' in window_info:
            rect = window_info['rect']
            self.window_config = WindowConfiguration.from_rect(
                rect,
                is_maximized=window_info.get('is_maximized', False),
                is_minimized=window_info.get('is_minimized', False)
            )
        
        self.modified_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary for serialization."""
        data = asdict(self)
        
        # Convert enums to values
        data['profile_type'] = self.profile_type.value
        if self.matching_criteria:
            data['matching_criteria']['strategy'] = self.matching_criteria.strategy.value
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Profile':
        """Create profile from dictionary."""
        # Convert enum values back
        data['profile_type'] = ProfileType(data.get('profile_type', ProfileType.WINDOW_CONFIG.value))
        
        if 'matching_criteria' in data and data['matching_criteria']:
            criteria_data = data['matching_criteria']
            criteria_data['strategy'] = MatchingStrategy(criteria_data['strategy'])
            data['matching_criteria'] = MatchingCriteria(**criteria_data)
        
        if 'window_config' in data and data['window_config']:
            data['window_config'] = WindowConfiguration(**data['window_config'])
        
        # Set default values for advanced features if not present
        advanced_fields = {
            'hotkey_enabled': False,
            'hotkey_combination': '',
            'hotkey_action': 'apply_profile',
            'lock_size': False,
            'lock_width': False,
            'lock_height': False,
            'lock_position': False,
            'mouse_constraint': False,
            'constraint_mode': 'strict',
            'constraint_escape_key': 'Escape'
        }
        
        for field, default_value in advanced_fields.items():
            if field not in data:
                data[field] = default_value
        
        profile = cls(**data)
        
        # Initialize tracking attributes
        profile._locked_windows = {}
        profile._constrained_windows = set()
        
        return profile
    
    def validate(self) -> Tuple[bool, List[str]]:
        """Validate profile data."""
        errors = []
        
        if not self.name.strip():
            errors.append("Profile name is required")
        
        if self.window_config and not self.window_config.validate():
            errors.append("Invalid window configuration")
        
        if self.matching_criteria:
            if self.matching_criteria.strategy == MatchingStrategy.EXACT_TITLE:
                if not self.matching_criteria.window_title_pattern:
                    errors.append("Exact title matching requires window title pattern")
            elif self.matching_criteria.strategy == MatchingStrategy.PROCESS_NAME:
                if not self.matching_criteria.process_name_pattern:
                    errors.append("Process name matching requires process name pattern")
            elif self.matching_criteria.strategy == MatchingStrategy.EXECUTABLE_PATH:
                if not self.matching_criteria.executable_path_pattern:
                    errors.append("Executable path matching requires an executable path")
            elif self.matching_criteria.strategy == MatchingStrategy.COMBINED:
                if not any([
                    self.matching_criteria.window_title_pattern,
                    self.matching_criteria.process_name_pattern,
                    self.matching_criteria.window_class_pattern,
                    self.matching_criteria.executable_path_pattern
                ]):
                    errors.append("Combined matching requires at least one criterion")
        
        return len(errors) == 0, errors

class ProfileManager:
    """Manages profiles with persistent storage and matching."""
    
    def __init__(self, storage_path: Optional[str] = None):
        """Initialize profile manager."""
        self.storage_path = Path(storage_path) if storage_path else Path("profiles")
        self.storage_path.mkdir(exist_ok=True)
        
        self.profiles_file = self.storage_path / "profiles.json"
        self.profiles: Dict[str, Profile] = {}
        
        # Load existing profiles
        self.load_profiles()
        
        logger.info(f"ProfileManager initialized with {len(self.profiles)} profiles")
    
    def create_profile(self, name: str, description: str = "", 
                      window_info: Dict[str, Any] = None,
                      matching_criteria: MatchingCriteria = None,
                      profile_type: ProfileType = None,
                      tags: List[str] = None,
                      auto_apply: bool = False,
                      enabled: bool = True,
                      window_config: WindowConfiguration = None) -> Profile:
        """Create a new profile."""
        if self.get_profile_by_name(name):
            raise ValueError(f"Profile with name '{name}' already exists")
        
        # Create window configuration from window info or use provided one
        if not window_config and window_info and 'rect' in window_info:
            window_config = WindowConfiguration.from_rect(
                window_info['rect'],
                is_maximized=window_info.get('is_maximized', False),
                is_minimized=window_info.get('is_minimized', False)
            )
        
        # Create default matching criteria if none provided
        if not matching_criteria and window_info:
            executable_path = window_info.get('executable_path', '')
            if executable_path:
                matching_criteria = MatchingCriteria(
                    strategy=MatchingStrategy.EXECUTABLE_PATH,
                    executable_path_pattern=executable_path
                )
            else:
                matching_criteria = MatchingCriteria(
                    strategy=MatchingStrategy.TITLE_CONTAINS,
                    window_title_pattern=window_info.get('title', ''),
                    process_name_pattern=window_info.get('process_name', '')
                )
        
        profile = Profile(
            name=name,
            description=description,
            window_config=window_config,
            matching_criteria=matching_criteria,
            profile_type=profile_type or ProfileType.WINDOW_CONFIG,
            tags=tags or [],
            auto_apply=auto_apply,
            enabled=enabled
        )
        
        # Validate profile
        is_valid, errors = profile.validate()
        if not is_valid:
            raise ValueError(f"Invalid profile: {', '.join(errors)}")
        
        self.profiles[profile.id] = profile
        self.save_profiles()
        
        logger.info(f"Created profile: {name} (ID: {profile.id})")
        return profile
    
    def get_profile(self, profile_id: str) -> Optional[Profile]:
        """Get profile by ID."""
        return self.profiles.get(profile_id)
    
    def get_profile_by_name(self, name: str) -> Optional[Profile]:
        """Get profile by name."""
        for profile in self.profiles.values():
            if profile.name == name:
                return profile
        return None
    
    def list_profiles(self, profile_type: ProfileType = None, 
                     enabled_only: bool = False) -> List[Profile]:
        """List profiles with optional filtering."""
        profiles = list(self.profiles.values())
        
        if profile_type:
            profiles = [p for p in profiles if p.profile_type == profile_type]
        
        if enabled_only:
            profiles = [p for p in profiles if p.enabled]
        
        # Sort by name
        return sorted(profiles, key=lambda p: p.name)
    
    def update_profile(self, profile_id: str, **updates) -> bool:
        """Update profile with new data."""
        profile = self.get_profile(profile_id)
        if not profile:
            return False
        
        # Update fields
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        profile.modified_at = time.time()
        
        # Validate updated profile
        is_valid, errors = profile.validate()
        if not is_valid:
            logger.error(f"Profile update validation failed: {', '.join(errors)}")
            return False
        
        self.save_profiles()
        logger.info(f"Updated profile: {profile.name}")
        return True
    
    def delete_profile(self, profile_id: str) -> bool:
        """Delete profile."""
        if profile_id in self.profiles:
            profile_name = self.profiles[profile_id].name
            del self.profiles[profile_id]
            self.save_profiles()
            logger.info(f"Deleted profile: {profile_name}")
            return True
        return False
    
    def find_matching_profiles(self, window_info: Dict[str, Any]) -> List[Profile]:
        """Find profiles that match the given window."""
        matching_profiles = []
        
        for profile in self.profiles.values():
            if profile.matches_window(window_info):
                matching_profiles.append(profile)
        
        # Sort by priority (if available) or by name
        matching_profiles.sort(key=lambda p: (
            -getattr(p.matching_criteria, 'priority', 50),
            p.name
        ))
        
        return matching_profiles
    
    def apply_profile(self, profile_id: str, window_info: Dict[str, Any]) -> bool:
        """Apply profile to window."""
        profile = self.get_profile(profile_id)
        if not profile:
            logger.error(f"Profile not found: {profile_id}")
            return False
        
        success = profile.apply_to_window(window_info)
        if success:
            self.save_profiles()  # Update metadata
        
        return success
    
    def auto_apply_profiles(self, windows_info: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Auto-apply profiles to matching windows."""
        results = {"applied": [], "failed": []}
        
        for window_info in windows_info:
            matching_profiles = self.find_matching_profiles(window_info)
            auto_apply_profiles = [p for p in matching_profiles if p.auto_apply]
            
            for profile in auto_apply_profiles:
                try:
                    if self.apply_profile(profile.id, window_info):
                        results["applied"].append(f"{profile.name} -> {window_info.get('title', 'Unknown')}")
                    else:
                        results["failed"].append(f"{profile.name} -> {window_info.get('title', 'Unknown')}")
                except Exception as e:
                    logger.error(f"Error applying profile {profile.name}: {e}")
                    results["failed"].append(f"{profile.name} -> Error: {e}")
        
        return results
    
    def apply_all_profiles(self, windows_info: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Apply all profiles to matching windows (for manual 'Apply All' action)."""
        results = {"applied": [], "failed": []}
        
        # 모든 프로필을 대상으로 매칭 시도
        for profile in self.profiles.values():
            for window_info in windows_info:
                try:
                    if profile.matches_window(window_info):
                        if self.apply_profile(profile.id, window_info):
                            results["applied"].append(f"{profile.name} -> {window_info.get('title', 'Unknown')}")
                        else:
                            results["failed"].append(f"{profile.name} -> {window_info.get('title', 'Unknown')}")
                        # 한 번 적용하면 다음 창으로
                        break
                except Exception as e:
                    logger.error(f"Error applying profile {profile.name}: {e}")
                    results["failed"].append(f"{profile.name} -> Error: {e}")
        
        return results
    
    def save_profiles(self) -> bool:
        """Save profiles to persistent storage."""
        temporary_file = self.profiles_file.with_suffix('.json.tmp')
        backup_file = self.profiles_file.with_suffix('.json.backup')

        try:
            profiles_data = {
                "version": "1.0",
                "created_at": time.time(),
                "profiles": {
                    profile_id: profile.to_dict() 
                    for profile_id, profile in self.profiles.items()
                }
            }

            self.profiles_file.parent.mkdir(parents=True, exist_ok=True)
            with open(temporary_file, 'w', encoding='utf-8') as file:
                json.dump(profiles_data, file, indent=2, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())

            # Keep the last known-good file before replacing it atomically.
            if self.profiles_file.exists():
                shutil.copy2(self.profiles_file, backup_file)

            os.replace(temporary_file, self.profiles_file)
            logger.debug(f"Saved {len(self.profiles)} profiles to {self.profiles_file}")
            return True

        except Exception as e:
            logger.error(f"Error saving profiles: {e}")
            return False

        finally:
            if temporary_file.exists():
                try:
                    temporary_file.unlink()
                except OSError:
                    logger.warning(f"Could not remove temporary profile file: {temporary_file}")

    def load_profiles(self):
        """Load profiles from persistent storage."""
        backup_file = self.profiles_file.with_suffix('.json.backup')
        candidate_files = [self.profiles_file, backup_file]

        if not any(candidate.exists() for candidate in candidate_files):
            logger.info("No existing profiles file found")
            return

        for source_file in candidate_files:
            if not source_file.exists():
                continue

            try:
                with open(source_file, 'r', encoding='utf-8') as file:
                    data = json.load(file)

                profiles_data = data.get("profiles", {})
                loaded_count = 0

                for profile_id, profile_dict in profiles_data.items():
                    try:
                        profile = Profile.from_dict(profile_dict)
                        self.profiles[profile_id] = profile
                        loaded_count += 1
                    except Exception as e:
                        logger.error(f"Error loading profile {profile_id}: {e}")

                if source_file == backup_file:
                    logger.warning(f"Recovered profiles from backup: {backup_file}")
                logger.info(f"Loaded {loaded_count} profiles from {source_file}")
                return

            except Exception as e:
                logger.error(f"Error loading profiles from {source_file}: {e}")
    
    def export_profiles(self, export_path: str, profile_ids: List[str] = None) -> bool:
        """Export profiles to file."""
        try:
            if profile_ids:
                export_profiles = {pid: self.profiles[pid] for pid in profile_ids if pid in self.profiles}
            else:
                export_profiles = self.profiles.copy()
            
            export_data = {
                "version": "1.0",
                "exported_at": time.time(),
                "profiles": {
                    profile_id: profile.to_dict()
                    for profile_id, profile in export_profiles.items()
                }
            }
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Exported {len(export_profiles)} profiles to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting profiles: {e}")
            return False
    
    def import_profiles(self, import_path: str, overwrite: bool = False) -> Tuple[int, int]:
        """Import profiles from file. Returns (imported_count, skipped_count)."""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            profiles_data = data.get("profiles", {})
            imported_count = 0
            skipped_count = 0
            
            for profile_id, profile_dict in profiles_data.items():
                try:
                    if profile_id in self.profiles and not overwrite:
                        skipped_count += 1
                        continue
                    
                    profile = Profile.from_dict(profile_dict)
                    self.profiles[profile_id] = profile
                    imported_count += 1
                    
                except Exception as e:
                    logger.error(f"Error importing profile {profile_id}: {e}")
                    skipped_count += 1
            
            if imported_count > 0:
                self.save_profiles()
            
            logger.info(f"Imported {imported_count} profiles, skipped {skipped_count}")
            return imported_count, skipped_count
            
        except Exception as e:
            logger.error(f"Error importing profiles: {e}")
            return 0, 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get profile statistics."""
        if not self.profiles:
            return {"total": 0}
        
        total = len(self.profiles)
        enabled = sum(1 for p in self.profiles.values() if p.enabled)
        auto_apply = sum(1 for p in self.profiles.values() if p.auto_apply)
        
        # Type distribution
        type_counts = {}
        for profile in self.profiles.values():
            ptype = profile.profile_type.value
            type_counts[ptype] = type_counts.get(ptype, 0) + 1
        
        # Usage statistics
        applied_profiles = [p for p in self.profiles.values() if p.applied_count > 0]
        most_used = max(applied_profiles, key=lambda p: p.applied_count) if applied_profiles else None
        
        return {
            "total": total,
            "enabled": enabled,
            "auto_apply": auto_apply,
            "type_distribution": type_counts,
            "most_used_profile": most_used.name if most_used else None,
            "most_used_count": most_used.applied_count if most_used else 0,
            "total_applications": sum(p.applied_count for p in self.profiles.values())
        }

# Global profile manager instance
default_profile_manager = ProfileManager()
