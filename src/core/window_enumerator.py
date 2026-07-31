"""
Window Enumeration Engine
=========================

High-performance window enumeration and information collection system.
Provides comprehensive window discovery with filtering, sorting, and 
advanced detection capabilities for various application types.

Key Features:
- Fast window enumeration with intelligent filtering
- UWP app detection and handling
- Process information collection and matching
- Hidden/system window filtering
- Real-time window monitoring capabilities
- Performance optimizations for large window counts
"""

import time
import psutil
import logging
from typing import List, Dict, Set, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import re

from .windows_api import WindowsAPI, WindowInfo, WindowsAPIError

logger = logging.getLogger(__name__)

class WindowType(Enum):
    """Window type classification."""
    NORMAL = "normal"
    UWP = "uwp"
    SYSTEM = "system"
    HIDDEN = "hidden"
    GAME = "game"
    BROWSER = "browser"
    OFFICE = "office"
    DEVELOPMENT = "development"
    MEDIA = "media"
    UTILITY = "utility"
    UNKNOWN = "unknown"

class FilterMode(Enum):
    """Window filtering modes."""
    ALL = "all"
    VISIBLE_ONLY = "visible_only"
    TITLED_ONLY = "titled_only"
    USER_WINDOWS = "user_windows"
    APPLICATIONS = "applications"
    GAMES = "games"

@dataclass
class ProcessInfo:
    """Extended process information."""
    pid: int
    name: str
    exe_path: str
    command_line: str
    create_time: float
    cpu_percent: float
    memory_mb: float
    is_system: bool
    parent_pid: int

@dataclass
class EnhancedWindowInfo:
    """Enhanced window information with process details and classification."""
    # Basic window info
    hwnd: int
    title: str
    class_name: str
    rect: 'WindowRect'
    is_visible: bool
    is_minimized: bool
    is_maximized: bool
    
    # Process information
    process_info: Optional[ProcessInfo] = None
    
    # Classification
    window_type: WindowType = WindowType.UNKNOWN
    
    # Additional properties
    z_order: int = 0
    last_updated: float = field(default_factory=time.time)
    is_responsive: bool = True
    has_menu: bool = False
    is_topmost: bool = False
    
    # Detection flags
    is_uwp_app: bool = False
    is_game: bool = False
    is_elevated: bool = False

class WindowClassifier:
    """Classifies windows by type based on various heuristics."""
    
    # Class name patterns for different window types
    UWP_CLASSES = {
        'ApplicationFrameWindow', 'Windows.UI.Core.CoreWindow', 
        'WinUIDesktopWin32WindowClass', 'ApplicationManager_DesktopShellWindow'
    }
    
    SYSTEM_CLASSES = {
        'Shell_TrayWnd', 'WorkerW', 'Shell_SecondaryTrayWnd', 'NotifyIconOverflowWindow',
        'TaskListThumbnailWnd', 'MSTaskSwWClass', 'Button', 'TopLevelWindowForOverflowXamlIsland',
        'Windows.UI.Composition.DesktopWindowContentBridge', 'MSCTFIME UI', 'IME'
    }
    
    BROWSER_CLASSES = {
        'Chrome_WidgetWin_1', 'MozillaWindowClass', 'ApplicationFrameWindow'
    }
    
    GAME_INDICATORS = {
        'classes': {'UnityWndClass', 'SDL_app', 'GLFW30'},
        'processes': {'steam.exe', 'origin.exe', 'uplay.exe', 'epicgameslauncher.exe'},
        'titles': ['steam', 'origin', 'uplay', 'epic games', 'battle.net', 'gog galaxy']
    }
    
    OFFICE_CLASSES = {
        'OpusApp', 'XLMAIN', 'PPTFrameClass', 'rctrl_renwnd32'
    }
    
    DEVELOPMENT_PROCESSES = {
        'code.exe', 'devenv.exe', 'pycharm64.exe', 'idea64.exe', 'atom.exe',
        'sublime_text.exe', 'notepad++.exe', 'Code.exe'
    }
    
    @classmethod
    def classify_window(cls, window_info: WindowInfo, process_info: Optional[ProcessInfo] = None) -> WindowType:
        """Classify a window based on its properties."""
        try:
            class_name = window_info.class_name.lower()
            title = window_info.title.lower()
            process_name = process_info.name.lower() if process_info else ""
            
            # System windows
            if any(sys_class.lower() in class_name for sys_class in cls.SYSTEM_CLASSES):
                return WindowType.SYSTEM
            
            # Hidden or invalid windows
            if not window_info.is_visible or not window_info.title.strip():
                return WindowType.HIDDEN
            
            # UWP applications
            if any(uwp_class.lower() in class_name for uwp_class in cls.UWP_CLASSES):
                return WindowType.UWP
            
            # Games
            if (any(game_class.lower() in class_name for game_class in cls.GAME_INDICATORS['classes']) or
                any(game_proc in process_name for game_proc in cls.GAME_INDICATORS['processes']) or
                any(game_title in title for game_title in cls.GAME_INDICATORS['titles'])):
                return WindowType.GAME
            
            # Browsers
            if any(browser_class.lower() in class_name for browser_class in cls.BROWSER_CLASSES):
                # Further distinguish by process name or title
                if 'chrome' in process_name or 'chrome' in title:
                    return WindowType.BROWSER
                elif 'firefox' in process_name or 'firefox' in title:
                    return WindowType.BROWSER
                elif 'edge' in process_name or 'edge' in title:
                    return WindowType.BROWSER
            
            # Office applications
            if any(office_class.lower() in class_name for office_class in cls.OFFICE_CLASSES):
                return WindowType.OFFICE
            
            # Development tools
            if any(dev_proc in process_name for dev_proc in cls.DEVELOPMENT_PROCESSES):
                return WindowType.DEVELOPMENT
            
            # Media applications
            if any(media_word in title for media_word in ['player', 'vlc', 'media', 'music', 'video']):
                return WindowType.MEDIA
            
            # Default to normal application
            return WindowType.NORMAL
            
        except Exception as e:
            logger.warning(f"Error classifying window {window_info.hwnd}: {e}")
            return WindowType.UNKNOWN

class ProcessManager:
    """Manages process information collection and caching."""
    
    def __init__(self):
        self._process_cache: Dict[int, ProcessInfo] = {}
        self._cache_lock = Lock()
        self._cache_timeout = 5.0  # Cache for 5 seconds
        self._last_update = 0.0
    
    def get_process_info(self, pid: int, force_refresh: bool = False) -> Optional[ProcessInfo]:
        """Get detailed process information with caching."""
        current_time = time.time()
        
        with self._cache_lock:
            # Check cache first
            if not force_refresh and pid in self._process_cache:
                cached_info = self._process_cache[pid]
                if current_time - self._last_update < self._cache_timeout:
                    return cached_info
            
            # Fetch fresh process info
            try:
                process = psutil.Process(pid)
                
                # Get process details
                process_info = ProcessInfo(
                    pid=pid,
                    name=process.name(),
                    exe_path=process.exe(),
                    command_line=' '.join(process.cmdline()),
                    create_time=process.create_time(),
                    cpu_percent=process.cpu_percent(),
                    memory_mb=process.memory_info().rss / 1024 / 1024,
                    is_system=self._is_system_process(process),
                    parent_pid=process.ppid()
                )
                
                # Cache the result
                self._process_cache[pid] = process_info
                return process_info
                
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                logger.debug(f"Could not get process info for PID {pid}: {e}")
                return None
            except Exception as e:
                logger.error(f"Error getting process info for PID {pid}: {e}")
                return None
    
    def _is_system_process(self, process: psutil.Process) -> bool:
        """Determine if a process is a system process."""
        try:
            # Check common system process characteristics
            if process.username() == 'NT AUTHORITY\\SYSTEM':
                return True
            
            exe_path = process.exe().lower()
            if 'windows\\system32' in exe_path or 'windows\\syswow64' in exe_path:
                return True
                
            system_processes = {
                'dwm.exe', 'winlogon.exe', 'csrss.exe', 'smss.exe', 'wininit.exe',
                'services.exe', 'lsass.exe', 'svchost.exe', 'spoolsv.exe'
            }
            
            return process.name().lower() in system_processes
            
        except (psutil.AccessDenied, AttributeError):
            return False
    
    def refresh_cache(self):
        """Force refresh of the process cache."""
        with self._cache_lock:
            self._process_cache.clear()
            self._last_update = 0.0

class WindowEnumerator:
    """
    High-performance window enumeration engine with advanced filtering and classification.
    
    Provides efficient window discovery, classification, and monitoring capabilities
    with support for various filtering modes and real-time updates.
    """
    
    def __init__(self, api: Optional[WindowsAPI] = None):
        """
        Initialize the window enumerator.
        
        Args:
            api: Windows API instance to use (creates default if None)
        """
        self.api = api or WindowsAPI()
        self.classifier = WindowClassifier()
        self.process_manager = ProcessManager()
        self._enumeration_lock = Lock()
        
        # Performance tracking
        self._last_enumeration_time = 0.0
        self._enumeration_count = 0
        self._average_enumeration_time = 0.0
        
        logger.info("Window enumerator initialized")
    
    def enumerate_windows(self, 
                         filter_mode: FilterMode = FilterMode.USER_WINDOWS,
                         include_process_info: bool = True,
                         max_workers: int = 4) -> List[EnhancedWindowInfo]:
        """
        Enumerate windows with comprehensive information collection.
        
        Args:
            filter_mode: Filtering mode to apply
            include_process_info: Whether to collect process information
            max_workers: Maximum threads for parallel processing
            
        Returns:
            List of enhanced window information objects
        """
        start_time = time.time()
        
        with self._enumeration_lock:
            try:
                # Collect basic window information
                basic_windows = self._collect_basic_windows()
                logger.debug(f"Collected {len(basic_windows)} basic windows")
                
                # Apply initial filtering
                filtered_windows = self._apply_filter(basic_windows, filter_mode)
                logger.debug(f"Filtered to {len(filtered_windows)} windows")
                
                # Enhance with process information and classification
                enhanced_windows = self._enhance_windows(filtered_windows, include_process_info, max_workers)
                
                # Final sorting by relevance
                enhanced_windows.sort(key=self._get_window_relevance_score, reverse=True)
                
                # Update performance metrics
                enumeration_time = time.time() - start_time
                self._update_performance_metrics(enumeration_time)
                
                logger.info(f"Enumerated {len(enhanced_windows)} windows in {enumeration_time:.3f}s")
                return enhanced_windows
                
            except Exception as e:
                logger.error(f"Error during window enumeration: {e}")
                raise WindowsAPIError(f"Window enumeration failed: {e}")
    
    def _collect_basic_windows(self) -> List[WindowInfo]:
        """Collect basic window information from all top-level windows."""
        windows = []
        
        def enum_callback(hwnd: int, lparam: int) -> bool:
            try:
                window_info = self.api.get_window_info(hwnd)
                if window_info:
                    windows.append(window_info)
            except Exception as e:
                logger.debug(f"Error getting info for window {hwnd}: {e}")
            return True
        
        self.api.enum_windows(enum_callback)
        return windows
    
    def _apply_filter(self, windows: List[WindowInfo], filter_mode: FilterMode) -> List[WindowInfo]:
        """Apply filtering based on the specified mode."""
        if filter_mode == FilterMode.ALL:
            return windows
        
        filtered = []
        for window in windows:
            try:
                # Basic visibility and validity checks
                if not self.api.is_window(window.hwnd):
                    continue
                
                if filter_mode == FilterMode.VISIBLE_ONLY:
                    if window.is_visible:
                        filtered.append(window)
                
                elif filter_mode == FilterMode.TITLED_ONLY:
                    if window.is_visible and window.title.strip():
                        filtered.append(window)
                
                elif filter_mode == FilterMode.USER_WINDOWS:
                    if (window.is_visible and 
                        window.title.strip() and 
                        not self._is_system_window(window)):
                        filtered.append(window)
                
                elif filter_mode == FilterMode.APPLICATIONS:
                    if (window.is_visible and 
                        window.title.strip() and 
                        not self._is_system_window(window) and
                        self._is_application_window(window)):
                        filtered.append(window)
                
                elif filter_mode == FilterMode.GAMES:
                    # Pre-filter for potential games (will be refined in classification)
                    if (window.is_visible and 
                        window.title.strip() and
                        self._might_be_game(window)):
                        filtered.append(window)
                        
            except Exception as e:
                logger.debug(f"Error filtering window {window.hwnd}: {e}")
                continue
        
        return filtered
    
    def _is_system_window(self, window: WindowInfo) -> bool:
        """Check if a window is a system window."""
        system_classes = {
            'shell_traywnd', 'workerw', 'progman', 'shell_secondarytraywnd',
            'notifyiconoverflowwindow', 'tasklistthumbnailwnd', 'msaskswwclass',
            'button', 'tooltips_class32', 'msctfime ui'
        }
        
        return (window.class_name.lower() in system_classes or
                window.title.lower() in ['', 'program manager', 'desktop'] or
                window.rect.width == 0 or window.rect.height == 0)
    
    def _is_application_window(self, window: WindowInfo) -> bool:
        """Check if window represents a main application window."""
        # Main application windows typically have:
        # - A meaningful title
        # - Reasonable size
        # - Standard window classes
        
        if (window.rect.width < 100 or window.rect.height < 50 or
            len(window.title.strip()) < 3):
            return False
        
        # Exclude obvious utility windows
        utility_indicators = ['tooltip', 'popup', 'menu', 'dropdown', 'contextmenu']
        class_lower = window.class_name.lower()
        title_lower = window.title.lower()
        
        return not any(indicator in class_lower or indicator in title_lower 
                      for indicator in utility_indicators)
    
    def _might_be_game(self, window: WindowInfo) -> bool:
        """Quick check if window might be a game (for pre-filtering)."""
        game_indicators = ['steam', 'origin', 'uplay', 'epic', 'battle.net', 'gog',
                          'game', 'unity', 'unreal', '.exe']
        
        title_lower = window.title.lower()
        return any(indicator in title_lower for indicator in game_indicators)
    
    def _enhance_windows(self, windows: List[WindowInfo], 
                        include_process_info: bool, 
                        max_workers: int) -> List[EnhancedWindowInfo]:
        """Enhance basic window information with process details and classification."""
        enhanced_windows = []
        
        def enhance_single_window(window: WindowInfo) -> Optional[EnhancedWindowInfo]:
            try:
                # Get process information if requested
                process_info = None
                if include_process_info:
                    thread_id, process_id = self.api.get_window_thread_process_id(window.hwnd)
                    if process_id > 0:
                        process_info = self.process_manager.get_process_info(process_id)
                
                # Classify the window
                window_type = self.classifier.classify_window(window, process_info)
                
                # Create enhanced window info
                enhanced = EnhancedWindowInfo(
                    hwnd=window.hwnd,
                    title=window.title,
                    class_name=window.class_name,
                    rect=window.rect,
                    is_visible=window.is_visible,
                    is_minimized=window.is_minimized,
                    is_maximized=window.is_maximized,
                    process_info=process_info,
                    window_type=window_type,
                    is_uwp_app=(window_type == WindowType.UWP),
                    is_game=(window_type == WindowType.GAME),
                    is_elevated=self._check_elevation(process_info) if process_info else False
                )
                
                return enhanced
                
            except Exception as e:
                logger.debug(f"Error enhancing window {window.hwnd}: {e}")
                return None
        
        # Use thread pool for parallel processing
        if max_workers > 1 and len(windows) > 10:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(enhance_single_window, windows))
                enhanced_windows = [result for result in results if result is not None]
        else:
            # Sequential processing for small lists or single-threaded mode
            for window in windows:
                enhanced = enhance_single_window(window)
                if enhanced:
                    enhanced_windows.append(enhanced)
        
        return enhanced_windows
    
    def _check_elevation(self, process_info: ProcessInfo) -> bool:
        """Check if a process is running with elevated privileges."""
        if not process_info:
            return False
        
        try:
            # Common elevated processes
            elevated_names = {'userinit.exe', 'winlogon.exe', 'services.exe', 'lsass.exe'}
            return process_info.name.lower() in elevated_names
        except:
            return False
    
    def _get_window_relevance_score(self, window: EnhancedWindowInfo) -> float:
        """Calculate relevance score for sorting windows."""
        score = 0.0
        
        # Base score for visible windows
        if window.is_visible:
            score += 10.0
        
        # Penalty for minimized windows
        if window.is_minimized:
            score -= 5.0
        
        # Bonus for windows with meaningful titles
        if len(window.title.strip()) > 5:
            score += 5.0
        
        # Window type bonuses
        type_scores = {
            WindowType.NORMAL: 8.0,
            WindowType.GAME: 9.0,
            WindowType.BROWSER: 7.0,
            WindowType.OFFICE: 6.0,
            WindowType.DEVELOPMENT: 6.0,
            WindowType.UWP: 5.0,
            WindowType.MEDIA: 4.0,
            WindowType.UTILITY: 3.0,
            WindowType.SYSTEM: 1.0,
            WindowType.HIDDEN: 0.0,
            WindowType.UNKNOWN: 2.0
        }
        score += type_scores.get(window.window_type, 0.0)
        
        # Size bonuses (larger windows are typically more important)
        window_area = window.rect.width * window.rect.height
        if window_area > 500000:  # Large windows
            score += 3.0
        elif window_area > 100000:  # Medium windows
            score += 1.0
        elif window_area < 10000:  # Very small windows
            score -= 2.0
        
        # Process-based bonuses
        if window.process_info:
            # Recently created processes might be more relevant
            age_hours = (time.time() - window.process_info.create_time) / 3600
            if age_hours < 1:
                score += 2.0
            elif age_hours < 24:
                score += 1.0
        
        return score
    
    def _update_performance_metrics(self, enumeration_time: float):
        """Update performance tracking metrics."""
        self._last_enumeration_time = enumeration_time
        self._enumeration_count += 1
        
        # Calculate running average
        if self._enumeration_count == 1:
            self._average_enumeration_time = enumeration_time
        else:
            alpha = 0.1  # Smoothing factor
            self._average_enumeration_time = (alpha * enumeration_time + 
                                            (1 - alpha) * self._average_enumeration_time)
    
    def get_window_by_title(self, title_pattern: str, exact_match: bool = False) -> Optional[EnhancedWindowInfo]:
        """Find a window by title pattern."""
        windows = self.enumerate_windows(FilterMode.TITLED_ONLY, include_process_info=False)
        
        for window in windows:
            if exact_match:
                if window.title == title_pattern:
                    return window
            else:
                if re.search(title_pattern, window.title, re.IGNORECASE):
                    return window
        
        return None
    
    def get_windows_by_process(self, process_name: str) -> List[EnhancedWindowInfo]:
        """Get all windows belonging to a specific process."""
        windows = self.enumerate_windows(FilterMode.USER_WINDOWS, include_process_info=True)
        
        matching_windows = []
        for window in windows:
            if (window.process_info and 
                window.process_info.name.lower() == process_name.lower()):
                matching_windows.append(window)
        
        return matching_windows
    
    def monitor_windows(self, callback: Callable[[List[EnhancedWindowInfo]], None], 
                       interval: float = 1.0, filter_mode: FilterMode = FilterMode.USER_WINDOWS):
        """
        Monitor windows and call callback when changes are detected.
        
        Args:
            callback: Function to call with window list updates
            interval: Monitoring interval in seconds
            filter_mode: Window filtering mode
        """
        import threading
        
        def monitor_loop():
            last_windows = set()
            
            while True:
                try:
                    current_windows = self.enumerate_windows(filter_mode, include_process_info=False)
                    current_set = {(w.hwnd, w.title) for w in current_windows}
                    
                    if current_set != last_windows:
                        callback(current_windows)
                        last_windows = current_set
                    
                    time.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Error in window monitoring: {e}")
                    time.sleep(interval)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        return monitor_thread
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            'last_enumeration_time': self._last_enumeration_time,
            'average_enumeration_time': self._average_enumeration_time,
            'enumeration_count': self._enumeration_count,
            'process_cache_size': len(self.process_manager._process_cache)
        }

# Create default instance
default_enumerator = WindowEnumerator()

# Convenience functions
def enumerate_windows(filter_mode: FilterMode = FilterMode.USER_WINDOWS, 
                     include_process_info: bool = True) -> List[EnhancedWindowInfo]:
    """Enumerate windows using the default enumerator."""
    return default_enumerator.enumerate_windows(filter_mode, include_process_info)

def find_window_by_title(title_pattern: str, exact_match: bool = False) -> Optional[EnhancedWindowInfo]:
    """Find a window by title using the default enumerator."""
    return default_enumerator.get_window_by_title(title_pattern, exact_match)

def get_windows_by_process(process_name: str) -> List[EnhancedWindowInfo]:
    """Get windows by process name using the default enumerator."""
    return default_enumerator.get_windows_by_process(process_name)