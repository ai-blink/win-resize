"""
Window Information Caching System
=================================

Provides intelligent caching for window information to improve performance
and reduce API calls during frequent enumerations.

Key Features:
- Time-based cache expiration
- Window handle validation
- Smart cache invalidation
- Memory-efficient storage
- Thread-safe operations
"""

import time
import threading
from typing import Dict, Optional, Set, List
from dataclasses import dataclass, field
from .windows_api import WindowInfo
from .window_enumerator import EnhancedWindowInfo

@dataclass
class CachedWindowInfo:
    """Cached window information with metadata."""
    window_info: EnhancedWindowInfo
    cached_time: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    is_valid: bool = True

class WindowCache:
    """
    Thread-safe window information cache with intelligent expiration.
    
    Provides caching for window enumeration results to improve performance
    for applications that frequently query window information.
    """
    
    def __init__(self, 
                 default_ttl: float = 5.0,
                 max_cache_size: int = 1000,
                 cleanup_interval: float = 30.0):
        """
        Initialize the window cache.
        
        Args:
            default_ttl: Default time-to-live in seconds
            max_cache_size: Maximum number of cached windows
            cleanup_interval: Cleanup interval in seconds
        """
        self._cache: Dict[int, CachedWindowInfo] = {}
        self._cache_lock = threading.RLock()
        self._default_ttl = default_ttl
        self._max_cache_size = max_cache_size
        self._cleanup_interval = cleanup_interval
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._invalidations = 0
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def get(self, hwnd: int, validate: bool = True) -> Optional[EnhancedWindowInfo]:
        """
        Get cached window information.
        
        Args:
            hwnd: Window handle
            validate: Whether to validate the cached entry
            
        Returns:
            Cached window information if available and valid
        """
        with self._cache_lock:
            if hwnd not in self._cache:
                self._misses += 1
                return None
            
            cached_info = self._cache[hwnd]
            current_time = time.time()
            
            # Check if cache entry is expired
            if current_time - cached_info.cached_time > self._default_ttl:
                del self._cache[hwnd]
                self._misses += 1
                return None
            
            # Validate if requested
            if validate and not self._validate_entry(cached_info):
                del self._cache[hwnd]
                self._invalidations += 1
                self._misses += 1
                return None
            
            # Update access statistics
            cached_info.access_count += 1
            cached_info.last_access = current_time
            self._hits += 1
            
            return cached_info.window_info
    
    def put(self, window_info: EnhancedWindowInfo, ttl: Optional[float] = None):
        """
        Cache window information.
        
        Args:
            window_info: Window information to cache
            ttl: Custom time-to-live (uses default if None)
        """
        with self._cache_lock:
            # Check cache size limit
            if len(self._cache) >= self._max_cache_size:
                self._evict_lru()
            
            cached_info = CachedWindowInfo(
                window_info=window_info,
                cached_time=time.time()
            )
            
            self._cache[window_info.hwnd] = cached_info
    
    def invalidate(self, hwnd: int):
        """Invalidate a specific cache entry."""
        with self._cache_lock:
            if hwnd in self._cache:
                del self._cache[hwnd]
                self._invalidations += 1
    
    def invalidate_all(self):
        """Invalidate all cache entries."""
        with self._cache_lock:
            count = len(self._cache)
            self._cache.clear()
            self._invalidations += count
    
    def bulk_put(self, windows: List[EnhancedWindowInfo]):
        """Cache multiple windows efficiently."""
        with self._cache_lock:
            for window_info in windows:
                self.put(window_info)
    
    def get_statistics(self) -> Dict[str, any]:
        """Get cache statistics."""
        with self._cache_lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests) if total_requests > 0 else 0.0
            
            return {
                'cache_size': len(self._cache),
                'max_cache_size': self._max_cache_size,
                'hits': self._hits,
                'misses': self._misses,
                'invalidations': self._invalidations,
                'hit_rate': hit_rate,
                'total_requests': total_requests
            }
    
    def _validate_entry(self, cached_info: CachedWindowInfo) -> bool:
        """Validate that a cached entry is still valid."""
        try:
            # For now, just check if it's marked as valid
            # In a full implementation, we might check if the window handle is still valid
            return cached_info.is_valid
        except:
            return False
    
    def _evict_lru(self):
        """Evict least recently used cache entry."""
        if not self._cache:
            return
        
        # Find the least recently used entry
        lru_hwnd = min(self._cache.keys(), 
                      key=lambda hwnd: self._cache[hwnd].last_access)
        
        del self._cache[lru_hwnd]
    
    def _cleanup_loop(self):
        """Background cleanup of expired entries."""
        while True:
            try:
                time.sleep(self._cleanup_interval)
                self._cleanup_expired()
            except Exception:
                # Silently continue on errors
                pass
    
    def _cleanup_expired(self):
        """Remove expired cache entries."""
        current_time = time.time()
        expired_hwnds = []
        
        with self._cache_lock:
            for hwnd, cached_info in self._cache.items():
                if current_time - cached_info.cached_time > self._default_ttl:
                    expired_hwnds.append(hwnd)
            
            for hwnd in expired_hwnds:
                del self._cache[hwnd]
                self._invalidations += 1

# Global cache instance
window_cache = WindowCache()