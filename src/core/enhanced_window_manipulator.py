"""
Enhanced Window Manipulator with Comprehensive Error Handling
============================================================

Enhanced version of the window manipulator that integrates the comprehensive
error handling and recovery system, providing robust operation with automatic
retry, rollback, and privilege escalation capabilities.

Key Features:
- Integrated error handling and recovery
- Automatic retry with exponential backoff
- Operation rollback on failure
- Privilege escalation handling
- Safe mode operations
- Comprehensive logging and diagnostics
"""

from typing import Dict, List, Optional, Tuple, Any, Union
import time
import logging
from dataclasses import dataclass

from .window_manipulator import WindowManipulator, WindowConstraints, WindowState
from .error_handler import (
    WindowsErrorHandler, handle_errors, RetryConfig, 
    ErrorSeverity, RecoveryStrategy, default_error_handler
)
from .privilege_error_handler import (
    PrivilegeErrorHandler, PrivilegeError, SafeModeRestriction,
    default_privilege_error_handler
)
from .windows_api import WindowsAPIError, WindowRect

logger = logging.getLogger(__name__)

@dataclass
class EnhancedOperationResult:
    """Result of enhanced window operation with error handling details."""
    success: bool
    result: Any = None
    error_info: Optional[Dict[str, Any]] = None
    attempts_made: int = 1
    total_time: float = 0.0
    recovery_used: Optional[str] = None
    warnings: List[str] = None

class EnhancedWindowManipulator(WindowManipulator):
    """
    Enhanced window manipulator with comprehensive error handling.
    """
    
    def __init__(self, enable_error_handling: bool = True, 
                 enable_privilege_handling: bool = True,
                 safe_mode: bool = False):
        """
        Initialize enhanced window manipulator.
        
        Args:
            enable_error_handling: Enable comprehensive error handling
            enable_privilege_handling: Enable privilege escalation handling
            safe_mode: Start in safe mode (read-only operations)
        """
        super().__init__()
        
        self.error_handler = default_error_handler if enable_error_handling else None
        self.privilege_handler = default_privilege_error_handler if enable_privilege_handling else None
        
        self._enable_error_handling = enable_error_handling
        self._enable_privilege_handling = enable_privilege_handling
        self._operation_context_stack = []
        
        # Configure retry settings for different operation types
        self._retry_configs = {
            "move": RetryConfig(max_attempts=3, base_delay=0.1, max_delay=2.0),
            "resize": RetryConfig(max_attempts=3, base_delay=0.1, max_delay=2.0),
            "state": RetryConfig(max_attempts=2, base_delay=0.2, max_delay=1.0),
            "query": RetryConfig(max_attempts=2, base_delay=0.05, max_delay=0.5),
            "default": RetryConfig(max_attempts=3, base_delay=0.1, max_delay=2.0)
        }
        
        # Set safe mode if requested
        if safe_mode and self.privilege_handler:
            self.privilege_handler.enable_safe_mode()
        
        logger.info(f"EnhancedWindowManipulator initialized (Error handling: {enable_error_handling}, "
                   f"Privilege handling: {enable_privilege_handling}, Safe mode: {safe_mode})")
    
    def _get_retry_config(self, operation_type: str) -> RetryConfig:
        """Get retry configuration for operation type."""
        return self._retry_configs.get(operation_type, self._retry_configs["default"])
    
    def _execute_with_error_handling(self, func, operation_name: str, 
                                   hwnd: int, operation_type: str = "default",
                                   allow_rollback: bool = True) -> EnhancedOperationResult:
        """
        Execute operation with comprehensive error handling.
        
        Args:
            func: Function to execute
            operation_name: Name of operation for logging
            hwnd: Target window handle
            operation_type: Type of operation for retry configuration
            allow_rollback: Whether to attempt rollback on failure
            
        Returns:
            EnhancedOperationResult with execution details
        """
        start_time = time.time()
        result = EnhancedOperationResult(success=False, warnings=[])
        
        # Record original window state for potential rollback
        original_state = {}
        operation_context = None
        
        if allow_rollback and self.error_handler:
            try:
                # Get current window state
                rect = self.get_window_rect(hwnd)
                if rect:
                    original_state = {
                        "rect": rect,
                        "is_minimized": self.is_window_minimized(hwnd),
                        "is_maximized": self.is_window_maximized(hwnd)
                    }
                
                operation_context = self.error_handler.record_operation_context(
                    operation_name, hwnd, original_state
                )
                
                # Add rollback action
                if original_state.get("rect"):
                    def rollback_action():
                        try:
                            orig_rect = original_state["rect"]
                            super(EnhancedWindowManipulator, self).move_window(
                                hwnd, orig_rect.left, orig_rect.top, 
                                orig_rect.width, orig_rect.height
                            )
                        except Exception as e:
                            logger.warning(f"Rollback failed: {e}")
                    
                    self.error_handler.add_rollback_action(operation_context, rollback_action)
                    
            except Exception as e:
                result.warnings.append(f"Could not prepare rollback: {e}")
                logger.debug(f"Rollback preparation failed: {e}")
        
        # Execute with appropriate error handling
        try:
            if self._enable_privilege_handling and self.privilege_handler:
                # Use privilege-aware execution
                execution_result = self.privilege_handler.execute_with_privilege_handling(
                    func, operation_name, hwnd, allow_elevation=True
                )
            elif self._enable_error_handling and self.error_handler:
                # Use standard error handling with retry
                retry_config = self._get_retry_config(operation_type)
                execution_result = self.error_handler.retry_with_backoff(
                    func, retry_config, {"operation": operation_name, "hwnd": hwnd}
                )
            else:
                # Direct execution without error handling
                execution_result = func()
            
            result.success = True
            result.result = execution_result
            result.total_time = time.time() - start_time
            
            logger.debug(f"Operation {operation_name} completed successfully in {result.total_time:.3f}s")
            
        except SafeModeRestriction as e:
            result.error_info = {
                "type": "SafeModeRestriction",
                "message": str(e),
                "safe_alternatives": getattr(e, 'safe_alternatives', [])
            }
            result.recovery_used = "safe_mode_restriction"
            logger.warning(f"Operation {operation_name} blocked by safe mode: {e}")
            
        except (PrivilegeError, PermissionError) as e:
            result.error_info = {
                "type": "PrivilegeError",
                "message": str(e),
                "requires_elevation": True
            }
            result.recovery_used = "privilege_error"
            logger.error(f"Privilege error in {operation_name}: {e}")
            
        except WindowsAPIError as e:
            result.error_info = {
                "type": "WindowsAPIError", 
                "message": str(e),
                "error_code": getattr(e, 'error_code', None)
            }
            
            # Attempt rollback if enabled
            if allow_rollback and operation_context and self.error_handler:
                try:
                    rollback_success = self.error_handler.execute_rollback(operation_context)
                    result.recovery_used = "rollback" if rollback_success else "rollback_failed"
                except Exception as rollback_error:
                    result.warnings.append(f"Rollback failed: {rollback_error}")
            
            logger.error(f"Windows API error in {operation_name}: {e}")
            
        except Exception as e:
            result.error_info = {
                "type": type(e).__name__,
                "message": str(e)
            }
            
            # Handle error through error handler if available
            if self.error_handler:
                error_info = self.error_handler.handle_error(e, {
                    "operation": operation_name,
                    "hwnd": hwnd
                })
                result.error_info["severity"] = error_info.severity.value
                result.error_info["category"] = error_info.category.value
                result.error_info["suggestions"] = error_info.suggested_actions
            
            logger.error(f"Unexpected error in {operation_name}: {e}")
        
        result.total_time = time.time() - start_time
        return result
    
    # Enhanced window manipulation methods
    
    def enhanced_move_window(self, hwnd: int, x: int, y: int, 
                           width: int = None, height: int = None, 
                           constraints: WindowConstraints = None) -> EnhancedOperationResult:
        """
        Move window with enhanced error handling.
        
        Args:
            hwnd: Window handle
            x, y: New position
            width, height: Optional new size
            constraints: Window constraints
            
        Returns:
            EnhancedOperationResult with operation details
        """
        def move_operation():
            return super(EnhancedWindowManipulator, self).move_window(
                hwnd, x, y, width, height, constraints
            )
        
        return self._execute_with_error_handling(
            move_operation, f"move_window({x}, {y})", hwnd, "move"
        )
    
    def enhanced_resize_window(self, hwnd: int, width: int, height: int,
                             constraints: WindowConstraints = None) -> EnhancedOperationResult:
        """
        Resize window with enhanced error handling.
        
        Args:
            hwnd: Window handle
            width, height: New size
            constraints: Window constraints
            
        Returns:
            EnhancedOperationResult with operation details
        """
        def resize_operation():
            return super(EnhancedWindowManipulator, self).resize_window(
                hwnd, width, height, constraints
            )
        
        return self._execute_with_error_handling(
            resize_operation, f"resize_window({width}x{height})", hwnd, "resize"
        )
    
    def enhanced_center_window(self, hwnd: int, monitor_index: int = None) -> EnhancedOperationResult:
        """
        Center window with enhanced error handling.
        
        Args:
            hwnd: Window handle
            monitor_index: Optional monitor index
            
        Returns:
            EnhancedOperationResult with operation details
        """
        def center_operation():
            return super(EnhancedWindowManipulator, self).center_window(hwnd, monitor_index)
        
        return self._execute_with_error_handling(
            center_operation, "center_window", hwnd, "move"
        )
    
    def enhanced_minimize_window(self, hwnd: int) -> EnhancedOperationResult:
        """
        Minimize window with enhanced error handling.
        
        Args:
            hwnd: Window handle
            
        Returns:
            EnhancedOperationResult with operation details
        """
        def minimize_operation():
            return self.set_window_state(hwnd, WindowState.MINIMIZED)
        
        return self._execute_with_error_handling(
            minimize_operation, "minimize_window", hwnd, "state", allow_rollback=False
        )
    
    def enhanced_maximize_window(self, hwnd: int) -> EnhancedOperationResult:
        """
        Maximize window with enhanced error handling.
        
        Args:
            hwnd: Window handle
            
        Returns:
            EnhancedOperationResult with operation details
        """
        def maximize_operation():
            return self.set_window_state(hwnd, WindowState.MAXIMIZED)
        
        return self._execute_with_error_handling(
            maximize_operation, "maximize_window", hwnd, "state", allow_rollback=False
        )
    
    def enhanced_restore_window(self, hwnd: int) -> EnhancedOperationResult:
        """
        Restore window with enhanced error handling.
        
        Args:
            hwnd: Window handle
            
        Returns:
            EnhancedOperationResult with operation details
        """
        def restore_operation():
            return self.set_window_state(hwnd, WindowState.NORMAL)
        
        return self._execute_with_error_handling(
            restore_operation, "restore_window", hwnd, "state", allow_rollback=False
        )
    
    def enhanced_snap_to_edge(self, hwnd: int, edge: str, 
                            monitor_index: int = None) -> EnhancedOperationResult:
        """
        Snap window to edge with enhanced error handling.
        
        Args:
            hwnd: Window handle
            edge: Edge to snap to ("left", "right", "top", "bottom")
            monitor_index: Optional monitor index
            
        Returns:
            EnhancedOperationResult with operation details
        """
        def snap_operation():
            return super(EnhancedWindowManipulator, self).snap_to_edge(
                hwnd, edge, monitor_index
            )
        
        return self._execute_with_error_handling(
            snap_operation, f"snap_to_{edge}", hwnd, "move"
        )
    
    # Safe query operations (always allowed, even in safe mode)
    
    def safe_get_window_info(self, hwnd: int) -> Dict[str, Any]:
        """
        Safely get window information with error handling.
        
        Args:
            hwnd: Window handle
            
        Returns:
            Dictionary with window information or error details
        """
        try:
            # Use the parent WindowManipulator methods directly
            info = {
                "hwnd": hwnd,
                "title": super().get_window_title(hwnd) if hasattr(super(), 'get_window_title') else "Unknown",
                "class_name": super().get_window_class_name(hwnd) if hasattr(super(), 'get_window_class_name') else "Unknown",
                "rect": super().get_window_rect(hwnd) if hasattr(super(), 'get_window_rect') else None,
                "is_visible": super().is_window_visible(hwnd) if hasattr(super(), 'is_window_visible') else False,
                "is_minimized": super().is_window_minimized(hwnd) if hasattr(super(), 'is_window_minimized') else False,
                "is_maximized": super().is_window_maximized(hwnd) if hasattr(super(), 'is_window_maximized') else False,
                "process_id": getattr(super(), 'get_window_process_id', lambda x: None)(hwnd)
            }
            return {"success": True, "info": info}
            
        except Exception as e:
            error_info = {"success": False, "error": str(e), "error_type": type(e).__name__}
            
            if self.error_handler:
                handled_error = self.error_handler.handle_error(e, {"operation": "get_window_info", "hwnd": hwnd})
                error_info.update({
                    "severity": handled_error.severity.value,
                    "user_message": handled_error.user_friendly_message,
                    "suggestions": handled_error.suggested_actions
                })
            
            return error_info
    
    # Batch operations with error handling
    
    def enhanced_batch_operation(self, operations: List[Dict[str, Any]]) -> List[EnhancedOperationResult]:
        """
        Execute multiple operations with individual error handling.
        
        Args:
            operations: List of operation dictionaries with keys:
                       - operation: Operation name
                       - hwnd: Window handle
                       - args: Positional arguments
                       - kwargs: Keyword arguments
                       
        Returns:
            List of EnhancedOperationResult for each operation
        """
        results = []
        
        for i, op in enumerate(operations):
            try:
                operation_name = op.get("operation")
                hwnd = op.get("hwnd")
                args = op.get("args", [])
                kwargs = op.get("kwargs", {})
                
                if not operation_name or not hwnd:
                    results.append(EnhancedOperationResult(
                        success=False,
                        error_info={"type": "InvalidOperation", "message": "Missing operation or hwnd"}
                    ))
                    continue
                
                # Get enhanced method
                method_name = f"enhanced_{operation_name}"
                if hasattr(self, method_name):
                    method = getattr(self, method_name)
                    result = method(hwnd, *args, **kwargs)
                else:
                    # Fallback to base method with error handling
                    base_method = getattr(super(EnhancedWindowManipulator, self), operation_name, None)
                    if base_method:
                        def operation():
                            return base_method(hwnd, *args, **kwargs)
                        
                        result = self._execute_with_error_handling(
                            operation, operation_name, hwnd
                        )
                    else:
                        result = EnhancedOperationResult(
                            success=False,
                            error_info={"type": "UnknownOperation", "message": f"Unknown operation: {operation_name}"}
                        )
                
                results.append(result)
                
            except Exception as e:
                results.append(EnhancedOperationResult(
                    success=False,
                    error_info={"type": type(e).__name__, "message": str(e)}
                ))
        
        return results
    
    # Error handling control methods
    
    def enable_safe_mode(self):
        """Enable safe mode - only read-only operations allowed."""
        if self.privilege_handler:
            self.privilege_handler.enable_safe_mode()
            logger.info("Safe mode enabled")
    
    def disable_safe_mode(self):
        """Disable safe mode - allow all operations based on privileges."""
        if self.privilege_handler:
            self.privilege_handler.disable_safe_mode()
            logger.info("Safe mode disabled")
    
    def is_safe_mode_enabled(self) -> bool:
        """Check if safe mode is enabled."""
        if self.privilege_handler:
            return self.privilege_handler.is_safe_mode_enabled()
        return False
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics."""
        stats = {"enhanced_manipulator": True}
        
        if self.error_handler:
            stats["general_errors"] = self.error_handler.get_error_statistics()
        
        if self.privilege_handler:
            stats["privilege_errors"] = self.privilege_handler.get_error_statistics()
        
        return stats
    
    def save_error_report(self, filename: str = None):
        """Save comprehensive error report."""
        if self.error_handler:
            self.error_handler.save_error_report(filename)

# Global enhanced manipulator instance
default_enhanced_manipulator = EnhancedWindowManipulator()

def get_enhanced_window_manipulator() -> EnhancedWindowManipulator:
    """
    Get the global enhanced window manipulator instance.
    
    Returns:
        EnhancedWindowManipulator: Global instance with error handling
    """
    global default_enhanced_manipulator
    if default_enhanced_manipulator is None:
        default_enhanced_manipulator = EnhancedWindowManipulator()
    return default_enhanced_manipulator