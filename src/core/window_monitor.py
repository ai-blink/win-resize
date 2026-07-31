"""
Window Monitoring Service
========================

Monitors system for new windows and triggers automatic profile application.
Provides real-time detection of window creation, focus changes, and process launches.

Key Features:
- Background thread-based monitoring
- Configurable detection intervals
- Window creation event detection
- Process launch monitoring
- Filtering to avoid unnecessary processing
"""

import threading
import time
import logging
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass
from enum import Enum
import ctypes
from ctypes import wintypes, windll

from .window_enumerator import WindowEnumerator, FilterMode
from .profile_manager import Profile, ProfileManager

logger = logging.getLogger(__name__)

class MonitoringMode(Enum):
    """Window monitoring modes."""
    POLLING = "polling"          # Regular interval checking
    EVENT_DRIVEN = "event_driven"  # Windows event hooks (future)
    HYBRID = "hybrid"           # Combination of both

@dataclass
class MonitoringConfig:
    """Configuration for window monitoring."""
    enabled: bool = True
    mode: MonitoringMode = MonitoringMode.POLLING
    polling_interval: float = 1.0  # seconds
    startup_delay: float = 2.0     # Wait time after window creation
    max_retries: int = 3
    retry_delay: float = 0.5
    filter_system_windows: bool = True
    filter_short_lived: bool = True
    minimum_window_size: tuple = (100, 100)

@dataclass
class WindowEvent:
    """Represents a window event."""
    event_type: str  # "created", "focused", "closed"
    hwnd: int
    window_info: Optional[object] = None  # WindowInfo from enumerator
    timestamp: float = 0.0
    processed: bool = False

class WindowMonitor:
    """
    Monitors system for new windows and manages automatic profile application.
    """
    
    def __init__(self, profile_manager: ProfileManager, config: MonitoringConfig = None):
        """Initialize the window monitor."""
        self.profile_manager = profile_manager
        self.config = config or MonitoringConfig()
        self.enumerator = WindowEnumerator()
        
        # Thread management
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        
        # Window tracking
        self._known_windows: Set[int] = set()
        self._pending_windows: Dict[int, WindowEvent] = {}
        self._processed_windows: Set[int] = set()
        
        # Callbacks
        self._profile_applied_callback: Optional[Callable] = None
        self._error_callback: Optional[Callable] = None
        
        # Statistics
        self.stats = {
            'windows_detected': 0,
            'profiles_applied': 0,
            'apply_failures': 0,
            'last_activity': None
        }
        
        logger.info("Window monitor initialized")
    
    def start(self) -> bool:
        """Start the window monitoring service."""
        if self._running:
            logger.warning("Window monitor is already running")
            return False
        
        try:
            # Initialize known windows
            self._initialize_known_windows()
            
            # Start monitoring thread
            self._stop_event.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="WindowMonitor",
                daemon=True
            )
            self._monitor_thread.start()
            self._running = True
            
            logger.info("Window monitor started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start window monitor: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop the window monitoring service."""
        if not self._running:
            return True
        
        try:
            self._stop_event.set()
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5.0)
            
            self._running = False
            logger.info("Window monitor stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping window monitor: {e}")
            return False
    
    def set_profile_applied_callback(self, callback: Callable[[int, Profile], None]):
        """Set callback for when a profile is applied."""
        self._profile_applied_callback = callback
    
    def set_error_callback(self, callback: Callable[[str, Exception], None]):
        """Set callback for errors."""
        self._error_callback = callback
    
    def _initialize_known_windows(self):
        """Initialize the set of currently known windows."""
        try:
            windows = self.enumerator.enumerate_windows(FilterMode.USER_WINDOWS, include_process_info=True)
            self._known_windows = {w.hwnd for w in windows if self._should_monitor_window(w)}
            logger.debug(f"Initialized with {len(self._known_windows)} known windows")
        except Exception as e:
            logger.error(f"Error initializing known windows: {e}")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        logger.info("Window monitoring loop started")
        
        while not self._stop_event.is_set():
            try:
                # Check for new windows
                self._check_for_new_windows()
                
                # Process pending windows (those waiting for delay)
                self._process_pending_windows()
                
                # Clean up old processed windows
                self._cleanup_processed_windows()
                
                # Wait for next cycle
                self._stop_event.wait(self.config.polling_interval)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                if self._error_callback:
                    self._error_callback("Monitor loop error", e)
        
        logger.info("Window monitoring loop stopped")
    
    def _check_for_new_windows(self):
        """Check for newly created windows."""
        try:
            current_windows = self.enumerator.enumerate_windows(FilterMode.USER_WINDOWS, include_process_info=True)
            current_hwnds = {w.hwnd for w in current_windows if self._should_monitor_window(w)}
            
            # Find new windows
            new_hwnds = current_hwnds - self._known_windows
            
            for hwnd in new_hwnds:
                # Get window info
                window_info = next((w for w in current_windows if w.hwnd == hwnd), None)
                if window_info:
                    self._on_window_created(window_info)
            
            # Update known windows
            self._known_windows = current_hwnds
            
        except Exception as e:
            logger.error(f"Error checking for new windows: {e}")
    
    def _should_monitor_window(self, window) -> bool:
        """Determine if a window should be monitored."""
        if not window.is_visible:
            return False
        
        if self.config.filter_system_windows:
            # Filter out system windows, taskbar, etc.
            if not window.title or len(window.title.strip()) < 2:
                return False
            
            # Skip common system windows
            system_classes = {
                'Shell_TrayWnd', 'DV2ControlHost', 'Windows.UI.Core.CoreWindow',
                'ApplicationFrameWindow', 'MSTaskSwWClass'
            }
            if hasattr(window, 'class_name') and window.class_name in system_classes:
                return False
        
        if self.config.minimum_window_size:
            min_w, min_h = self.config.minimum_window_size
            if window.rect.width < min_w or window.rect.height < min_h:
                return False
        
        return True
    
    def _on_window_created(self, window):
        """Handle window creation event."""
        try:
            # Get process name from process_info if available
            process_name = "Unknown"
            if hasattr(window, 'process_info') and window.process_info:
                process_name = window.process_info.name
            elif hasattr(window, 'process_name'):
                process_name = window.process_name
            
            logger.debug(f"New window detected: {window.title} ({process_name})")
            
            # Create window event
            event = WindowEvent(
                event_type="created",
                hwnd=window.hwnd,
                window_info=window,
                timestamp=time.time()
            )
            
            # Add to pending windows with delay
            self._pending_windows[window.hwnd] = event
            self.stats['windows_detected'] += 1
            
        except Exception as e:
            logger.error(f"Error handling window creation: {e}")
    
    def _process_pending_windows(self):
        """Process windows that have been waiting for the startup delay."""
        current_time = time.time()
        to_process = []
        
        for hwnd, event in list(self._pending_windows.items()):
            if current_time - event.timestamp >= self.config.startup_delay:
                to_process.append(hwnd)
        
        for hwnd in to_process:
            event = self._pending_windows.pop(hwnd, None)
            if event:
                self._apply_matching_profile(event)
    
    def _apply_matching_profile(self, event: WindowEvent):
        """Find and apply matching profile for a window."""
        try:
            window = event.window_info
            if not window:
                return
            
            # Find matching profiles
            matching_profiles = self._find_matching_profiles(window)
            
            if not matching_profiles:
                logger.info(f"No matching profiles for window '{window.title}'")
                return
            
            auto_profiles = [
                profile for profile in matching_profiles if getattr(profile, 'auto_apply', False)
            ]
            if not auto_profiles:
                logger.info(f"No automatic profile is enabled for window '{window.title}'")
                return

            profile = auto_profiles[0]
            logger.info(f"Selected automatic profile: '{profile.name}' for window '{window.title}'")
            
            logger.info(f"Profile '{profile.name}' has auto-apply enabled, applying...")
            
            # Apply the profile
            success = self._apply_profile_to_window(window, profile)
            
            if success:
                self.stats['profiles_applied'] += 1
                self.stats['last_activity'] = time.time()
                logger.info(f"Applied profile '{profile.name}' to window '{window.title}'")
                
                if self._profile_applied_callback:
                    self._profile_applied_callback(window.hwnd, profile)
            else:
                self.stats['apply_failures'] += 1
                logger.warning(f"Failed to apply profile '{profile.name}' to window '{window.title}'")
            
            # Mark as processed
            self._processed_windows.add(window.hwnd)
            
        except Exception as e:
            logger.error(f"Error applying matching profile: {e}")
            self.stats['apply_failures'] += 1
    
    def _find_matching_profiles(self, window) -> List[Profile]:
        """Find profiles that match the given window."""
        matching_profiles = []
        
        try:
            profiles = self.profile_manager.list_profiles()
            
            for profile in profiles:
                if self._profile_matches_window(profile, window):
                    matching_profiles.append(profile)
            
            # Sort by priority (more specific matches first)
            matching_profiles.sort(key=lambda p: self._get_match_priority(p, window), reverse=True)
            
        except Exception as e:
            logger.error(f"Error finding matching profiles: {e}")
        
        return matching_profiles
    
    def _profile_matches_window(self, profile: Profile, window) -> bool:
        """Check if a profile matches a window."""
        try:
            process_name = "Unknown"
            if hasattr(window, 'process_info') and window.process_info:
                process_name = window.process_info.name
            elif hasattr(window, 'process_name'):
                process_name = window.process_name
            window_info = {
                'hwnd': getattr(window, 'hwnd', None),
                'title': getattr(window, 'title', ''),
                'process_name': process_name,
                'executable_path': (
                    getattr(window.process_info, 'exe_path', '')
                    if hasattr(window, 'process_info') and window.process_info else ''
                ),
                'class_name': getattr(window, 'class_name', ''),
                'rect': getattr(window, 'rect', None),
            }
            return profile.matches_window(window_info)
            
        except Exception as e:
            logger.error(f"Error checking profile match: {e}")
            return False
    
    def _get_match_priority(self, profile: Profile, window) -> int:
        """Get the priority score for a profile match (higher = better match)."""
        priority = 0
        
        try:
            criteria = profile.matching_criteria
            
            # Get process name from window info
            process_name = "Unknown"
            if hasattr(window, 'process_info') and window.process_info:
                process_name = window.process_info.name
            elif hasattr(window, 'process_name'):
                process_name = window.process_name
            
            # Exact title match gets highest priority
            if criteria.window_title_pattern and criteria.window_title_pattern.lower() == window.title.lower():
                priority += 100
            elif criteria.window_title_pattern and criteria.window_title_pattern.lower() in window.title.lower():
                priority += 50
            
            # Process name match
            if criteria.process_name_pattern and criteria.process_name_pattern.lower() == process_name.lower():
                priority += 80
            elif criteria.process_name_pattern and criteria.process_name_pattern.lower() in process_name.lower():
                priority += 40

            executable_path = (
                getattr(window.process_info, 'exe_path', '')
                if hasattr(window, 'process_info') and window.process_info else ''
            )
            if criteria.executable_path_pattern and criteria._match_executable_path({
                'executable_path': executable_path
            }):
                priority += 120
            
            # Class name match (if available)
            if (
                getattr(criteria, 'window_class_pattern', None)
                and hasattr(window, 'class_name')
            ):
                if criteria.window_class_pattern == window.class_name:
                    priority += 90
                elif criteria.window_class_pattern in window.class_name:
                    priority += 45
            
        except Exception as e:
            logger.error(f"Error calculating match priority: {e}")
        
        return priority
    
    def _apply_profile_to_window(self, window, profile: Profile) -> bool:
        """Apply a profile to a window with retry logic."""
        process_name = "Unknown"
        if hasattr(window, 'process_info') and window.process_info:
            process_name = window.process_info.name
        elif hasattr(window, 'process_name'):
            process_name = window.process_name

        window_info = {
            'hwnd': window.hwnd,
            'title': getattr(window, 'title', ''),
            'process_name': process_name,
            'executable_path': (
                getattr(window.process_info, 'exe_path', '')
                if hasattr(window, 'process_info') and window.process_info else ''
            ),
            'class_name': getattr(window, 'class_name', ''),
            'rect': getattr(window, 'rect', None),
        }
        for attempt in range(self.config.max_retries):
            try:
                if self.profile_manager.apply_profile(profile.id, window_info):
                    return True
                logger.warning(
                    f"Profile application attempt {attempt + 1} failed for window {window.hwnd}"
                )
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay)
                
            except Exception as e:
                logger.error(f"Error applying profile (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay)
        
        return False
    
    def _cleanup_processed_windows(self):
        """Clean up old processed windows to prevent memory leaks."""
        # Keep only recent processed windows (last hour)
        current_time = time.time()
        cutoff_time = current_time - 3600  # 1 hour
        
        # This is a simplified cleanup - in a real implementation,
        # we'd need to track timestamps for processed windows
        if len(self._processed_windows) > 1000:
            # Keep only the most recent 500
            recent_windows = list(self._processed_windows)[-500:]
            self._processed_windows = set(recent_windows)
    
    def get_statistics(self) -> Dict:
        """Get monitoring statistics."""
        return {
            **self.stats,
            'is_running': self._running,
            'pending_windows': len(self._pending_windows),
            'known_windows': len(self._known_windows),
            'processed_windows': len(self._processed_windows)
        }
    
    def force_scan(self):
        """Force an immediate scan for new windows."""
        if self._running:
            try:
                self._check_for_new_windows()
                self._process_pending_windows()
                logger.info("Forced scan completed")
            except Exception as e:
                logger.error(f"Error in forced scan: {e}")


# Global instance for easy access
_default_monitor: Optional[WindowMonitor] = None

def get_default_monitor(profile_manager: ProfileManager = None) -> WindowMonitor:
    """Get or create the default window monitor instance."""
    global _default_monitor
    if _default_monitor is None and profile_manager:
        _default_monitor = WindowMonitor(profile_manager)
    return _default_monitor
