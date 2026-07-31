"""
Process Monitor System
======================

Real-time process monitoring system for automatic profile application.
Detects new application launches and applies matching profiles automatically.

Key Features:
- WMI-based process creation event detection
- High-performance event processing
- Delayed application for window load completion
- Memory-efficient event handling
- Multi-process concurrent processing
"""

import sys
import os
import time
import threading
import logging
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from queue import Queue, Empty
from pathlib import Path
import hashlib
import weakref

try:
    import wmi
    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False
    
import psutil
from core.profile_manager import default_profile_manager
from core.window_enumerator import WindowEnumerator, FilterMode
from core.enhanced_window_manipulator import EnhancedWindowManipulator

logger = logging.getLogger(__name__)

@dataclass
class ProcessEvent:
    """Process creation event data."""
    pid: int
    process_name: str
    executable_path: str
    command_line: str
    creation_time: float
    parent_pid: int = 0
    user: str = ""
    
    def __post_init__(self):
        """Generate unique event ID."""
        content = f"{self.pid}_{self.process_name}_{self.creation_time}"
        self.event_id = hashlib.md5(content.encode()).hexdigest()[:16]

@dataclass 
class MonitoringConfig:
    """Configuration for process monitoring."""
    enabled: bool = True
    detection_delay: float = 2.0  # Seconds to wait before applying profiles
    max_queue_size: int = 1000
    worker_threads: int = 2
    excluded_processes: Set[str] = field(default_factory=lambda: {
        'dwm.exe', 'csrss.exe', 'winlogon.exe', 'services.exe',
        'smss.exe', 'wininit.exe', 'lsass.exe', 'svchost.exe'
    })
    included_patterns: List[str] = field(default_factory=list)
    memory_limit_mb: int = 100
    
class ProcessMonitor:
    """High-performance process monitoring system."""
    
    def __init__(self, config: MonitoringConfig = None):
        """Initialize process monitor."""
        self.config = config or MonitoringConfig()
        self.profile_manager = default_profile_manager
        self.window_manipulator = EnhancedWindowManipulator()
        self.window_enumerator = WindowEnumerator()
        
        # Event processing
        self.event_queue = Queue(maxsize=self.config.max_queue_size)
        self.processed_events: Set[str] = set()
        self.recent_processes: Dict[int, ProcessEvent] = {}
        
        # Threading
        self.monitor_thread = None
        self.worker_threads: List[threading.Thread] = []
        self.running = False
        self.stats_lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'events_processed': 0,
            'profiles_applied': 0,
            'errors': 0,
            'start_time': None,
            'last_event_time': None
        }
        
        # Callbacks
        self.event_callbacks: List[Callable] = []
        self.profile_callbacks: List[Callable] = []
        
        logger.info("ProcessMonitor initialized")
    
    def start(self) -> bool:
        """Start process monitoring."""
        if self.running:
            logger.warning("Process monitor already running")
            return False
        
        try:
            self.running = True
            self.stats['start_time'] = time.time()
            
            # Start WMI monitoring thread
            if WMI_AVAILABLE:
                self.monitor_thread = threading.Thread(
                    target=self._wmi_monitor_worker,
                    name="ProcessMonitor-WMI",
                    daemon=True
                )
            else:
                self.monitor_thread = threading.Thread(
                    target=self._polling_monitor_worker,
                    name="ProcessMonitor-Polling", 
                    daemon=True
                )
            
            self.monitor_thread.start()
            
            # Start worker threads
            for i in range(self.config.worker_threads):
                worker = threading.Thread(
                    target=self._event_worker,
                    name=f"ProcessMonitor-Worker-{i}",
                    daemon=True
                )
                worker.start()
                self.worker_threads.append(worker)
            
            logger.info(f"Process monitor started with {self.config.worker_threads} workers")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start process monitor: {e}")
            self.running = False
            return False
    
    def stop(self):
        """Stop process monitoring."""
        if not self.running:
            return
        
        logger.info("Stopping process monitor")
        self.running = False
        
        # Wait for threads to finish
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        for worker in self.worker_threads:
            if worker.is_alive():
                worker.join(timeout=2)
        
        # Clear data
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except Empty:
                break
        
        self.processed_events.clear()
        self.recent_processes.clear()
        self.worker_threads.clear()
        
        logger.info("Process monitor stopped")
    
    def _wmi_monitor_worker(self):
        """WMI-based process monitoring worker."""
        try:
            logger.info("Starting WMI process monitoring")
            c = wmi.WMI()
            
            # Create process watcher
            process_watcher = c.Win32_Process.watch_for("creation")
            
            while self.running:
                try:
                    # Wait for process creation event
                    new_process = process_watcher(timeout_ms=1000)
                    
                    if new_process and self.running:
                        self._handle_wmi_event(new_process)
                        
                except wmi.x_wmi_timed_out:
                    continue
                except Exception as e:
                    logger.error(f"WMI monitoring error: {e}")
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"WMI monitor worker failed: {e}")
            # Fall back to polling if WMI fails
            self._polling_monitor_worker()
    
    def _polling_monitor_worker(self):
        """Polling-based process monitoring worker."""
        logger.info("Starting polling process monitoring")
        known_pids = set()
        
        # Get initial process list
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                known_pids.add(proc.info['pid'])
        except:
            pass
        
        while self.running:
            try:
                current_pids = set()
                new_pids = set()
                
                # Get current processes
                for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'create_time', 'ppid', 'username']):
                    try:
                        pid = proc.info['pid']
                        current_pids.add(pid)
                        
                        if pid not in known_pids:
                            new_pids.add(pid)
                            self._handle_polling_event(proc.info)
                            
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                known_pids = current_pids
                
                # Sleep between polls
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Polling monitor error: {e}")
                time.sleep(2)
    
    def _handle_wmi_event(self, wmi_process):
        """Handle WMI process creation event."""
        try:
            event = ProcessEvent(
                pid=int(wmi_process.ProcessId),
                process_name=wmi_process.Name or "",
                executable_path=wmi_process.ExecutablePath or "",
                command_line=wmi_process.CommandLine or "",
                creation_time=time.time(),
                parent_pid=int(wmi_process.ParentProcessId or 0)
            )
            
            self._queue_event(event)
            
        except Exception as e:
            logger.error(f"Error handling WMI event: {e}")
    
    def _handle_polling_event(self, proc_info):
        """Handle polling-based process event."""
        try:
            event = ProcessEvent(
                pid=proc_info['pid'],
                process_name=proc_info['name'] or "",
                executable_path=proc_info['exe'] or "",
                command_line=' '.join(proc_info['cmdline'] or []),
                creation_time=proc_info['create_time'],
                parent_pid=proc_info['ppid'] or 0,
                user=proc_info['username'] or ""
            )
            
            self._queue_event(event)
            
        except Exception as e:
            logger.error(f"Error handling polling event: {e}")
    
    def _queue_event(self, event: ProcessEvent):
        """Queue process event for processing."""
        # Skip if already processed
        if event.event_id in self.processed_events:
            return
        
        # Filter excluded processes
        if event.process_name.lower() in self.config.excluded_processes:
            return
        
        # Filter by included patterns if specified
        if self.config.included_patterns:
            if not any(pattern.lower() in event.process_name.lower() 
                      for pattern in self.config.included_patterns):
                return
        
        try:
            self.event_queue.put_nowait(event)
            self.processed_events.add(event.event_id)
            self.recent_processes[event.pid] = event
            
            # Limit recent processes memory
            if len(self.recent_processes) > 1000:
                oldest_pids = sorted(self.recent_processes.keys())[:500]
                for pid in oldest_pids:
                    del self.recent_processes[pid]
                    
        except:
            # Queue full - skip event
            pass
    
    def _event_worker(self):
        """Process events from queue."""
        while self.running:
            try:
                event = self.event_queue.get(timeout=1)
                if event:
                    self._process_event(event)
                    
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Event worker error: {e}")
                time.sleep(0.1)
    
    def _process_event(self, event: ProcessEvent):
        """Process a single event."""
        try:
            with self.stats_lock:
                self.stats['events_processed'] += 1
                self.stats['last_event_time'] = time.time()
            
            logger.debug(f"Processing event: {event.process_name} (PID: {event.pid})")
            
            # Call event callbacks
            for callback in self.event_callbacks:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Event callback error: {e}")
            
            # Wait for application to fully load
            if self.config.detection_delay > 0:
                time.sleep(self.config.detection_delay)
            
            # Find matching profiles
            matching_profiles = self._find_matching_profiles(event)
            
            if matching_profiles:
                self._apply_profiles_to_process(event, matching_profiles)
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            with self.stats_lock:
                self.stats['errors'] += 1
    
    def _find_matching_profiles(self, event: ProcessEvent) -> List:
        """Find profiles matching the process event."""
        try:
            # Get windows for this process
            windows = self.window_enumerator.enumerate_windows(
                FilterMode.USER_WINDOWS, 
                include_process_info=True
            )
            
            process_windows = [
                w for w in windows 
                if w.process_info and w.process_info.pid == event.pid
            ]
            
            if not process_windows:
                return []
            
            # Find matching profiles for each window
            matching_profiles = []
            
            for window in process_windows:
                window_info = {
                    'hwnd': window.hwnd,
                    'title': window.title,
                    'process_name': event.process_name,
                    'executable_path': event.executable_path,
                    'class_name': getattr(window, 'class_name', ''),
                    'rect': window.rect
                }
                
                profiles = self.profile_manager.find_matching_profiles(window_info)
                auto_profiles = [p for p in profiles if p.auto_apply and p.enabled]
                
                if auto_profiles:
                    matching_profiles.extend([(window, profile) for profile in auto_profiles])
            
            return matching_profiles
            
        except Exception as e:
            logger.error(f"Error finding matching profiles: {e}")
            return []
    
    def _apply_profiles_to_process(self, event: ProcessEvent, matching_profiles: List):
        """Apply profiles to process windows."""
        try:
            applied_count = 0
            
            for window, profile in matching_profiles:
                try:
                    # Get current window info
                    window_info = {
                        'hwnd': window.hwnd,
                        'title': window.title,
                        'process_name': event.process_name,
                        'rect': window.rect
                    }
                    
                    # Apply profile
                    if self.profile_manager.apply_profile(profile.id, window_info):
                        # Apply window configuration using manipulator
                        if profile.window_config:
                            success = self.window_manipulator.move_window(
                                window.hwnd,
                                profile.window_config.x,
                                profile.window_config.y,
                                profile.window_config.width,
                                profile.window_config.height
                            )
                            
                            if success:
                                applied_count += 1
                                logger.info(f"Applied profile '{profile.name}' to {event.process_name}")
                                
                                # Call profile callbacks
                                for callback in self.profile_callbacks:
                                    try:
                                        callback(profile, window_info)
                                    except Exception as e:
                                        logger.error(f"Profile callback error: {e}")
                
                except Exception as e:
                    logger.error(f"Error applying profile '{profile.name}': {e}")
            
            if applied_count > 0:
                with self.stats_lock:
                    self.stats['profiles_applied'] += applied_count
                    
        except Exception as e:
            logger.error(f"Error applying profiles to process: {e}")
    
    def add_event_callback(self, callback: Callable):
        """Add callback for process events."""
        self.event_callbacks.append(callback)
    
    def add_profile_callback(self, callback: Callable):
        """Add callback for profile applications.""" 
        self.profile_callbacks.append(callback)
    
    def get_statistics(self) -> Dict:
        """Get monitoring statistics."""
        with self.stats_lock:
            stats = self.stats.copy()
        
        if stats['start_time']:
            stats['uptime'] = time.time() - stats['start_time']
        else:
            stats['uptime'] = 0
            
        stats['queue_size'] = self.event_queue.qsize()
        stats['recent_processes'] = len(self.recent_processes)
        stats['memory_usage'] = self._get_memory_usage()
        stats['is_running'] = self.running
        
        return stats
    
    def _get_memory_usage(self) -> float:
        """Get memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except:
            return 0.0
    
    def set_config(self, config: MonitoringConfig):
        """Update monitoring configuration."""
        self.config = config
        logger.info("Process monitor configuration updated")
    
    def clear_cache(self):
        """Clear processed events cache."""
        self.processed_events.clear()
        self.recent_processes.clear()
        logger.info("Process monitor cache cleared")

# Global process monitor instance
default_process_monitor = ProcessMonitor()

if __name__ == "__main__":
    # Test the process monitor
    import logging
    logging.basicConfig(level=logging.INFO)
    
    config = MonitoringConfig(
        detection_delay=1.0,
        worker_threads=1
    )
    
    monitor = ProcessMonitor(config)
    
    def on_event(event):
        print(f"Process detected: {event.process_name} (PID: {event.pid})")
    
    def on_profile(profile, window_info):
        print(f"Profile applied: {profile.name} -> {window_info.get('title', 'Unknown')}")
    
    monitor.add_event_callback(on_event)
    monitor.add_profile_callback(on_profile)
    
    try:
        monitor.start()
        print("Process monitor running. Press Ctrl+C to stop.")
        
        while True:
            time.sleep(5)
            stats = monitor.get_statistics()
            print(f"Stats: {stats['events_processed']} events, {stats['profiles_applied']} applied")
            
    except KeyboardInterrupt:
        print("\nStopping monitor...")
    finally:
        monitor.stop()