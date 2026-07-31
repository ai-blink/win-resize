"""
Comprehensive Error Handling and Recovery System
===============================================

Robust exception handling framework for window manipulation operations
with Win32 error code mapping, automatic retry logic, rollback mechanisms,
and user-friendly error reporting.

Key Features:
- Win32 error code mapping and translation
- Automatic retry with exponential backoff
- Operation rollback mechanisms
- User-friendly error messages
- Comprehensive logging and diagnostics
- Privilege escalation handling
- Recovery strategies for common failures
"""

import time
import logging
import traceback
import threading
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import json
from pathlib import Path

# Win32 error codes - most common ones
WIN32_ERROR_CODES = {
    0: "ERROR_SUCCESS",
    1: "ERROR_INVALID_FUNCTION", 
    2: "ERROR_FILE_NOT_FOUND",
    3: "ERROR_PATH_NOT_FOUND",
    5: "ERROR_ACCESS_DENIED",
    6: "ERROR_INVALID_HANDLE",
    87: "ERROR_INVALID_PARAMETER",
    122: "ERROR_INSUFFICIENT_BUFFER",
    1400: "ERROR_INVALID_WINDOW_HANDLE",
    1401: "ERROR_INVALID_MENU_HANDLE",
    1402: "ERROR_INVALID_CURSOR_HANDLE",
    1403: "ERROR_INVALID_ACCEL_HANDLE",
    1404: "ERROR_INVALID_HOOK_HANDLE",
    1405: "ERROR_INVALID_DWP_HANDLE",
    1406: "ERROR_TLW_WITH_WSCHILD",
    1407: "ERROR_CANNOT_FIND_WND_CLASS",
    1408: "ERROR_WINDOW_OF_OTHER_THREAD",
    1409: "ERROR_HOTKEY_ALREADY_REGISTERED",
    1410: "ERROR_CLASS_ALREADY_EXISTS",
    1411: "ERROR_CLASS_DOES_NOT_EXIST",
    1412: "ERROR_CLASS_HAS_WINDOWS",
    1413: "ERROR_INVALID_INDEX",
    1414: "ERROR_INVALID_ICON_HANDLE",
    1415: "ERROR_USING_PRIVATE_DIALOG",
    1416: "ERROR_LISTBOX_ID_NOT_FOUND",
    1417: "ERROR_NO_WILDCARD_CHARACTERS",
    1418: "ERROR_THREAD_1_INACTIVE",
    1419: "ERROR_HOTKEY_NOT_REGISTERED",
    1420: "ERROR_WINDOW_NOT_DIALOG",
    1421: "ERROR_CONTROL_ID_NOT_FOUND",
    1422: "ERROR_INVALID_COMBOBOX_MESSAGE",
    1423: "ERROR_WINDOW_NOT_COMBOBOX",
    1424: "ERROR_INVALID_EDIT_HEIGHT",
    1425: "ERROR_DC_NOT_FOUND",
    1426: "ERROR_INVALID_HOOK_FILTER",
    1427: "ERROR_INVALID_FILTER_PROC",
    1428: "ERROR_HOOK_NEEDS_HMOD",
    1429: "ERROR_GLOBAL_ONLY_HOOK",
    1430: "ERROR_JOURNAL_HOOK_SET",
    1431: "ERROR_HOOK_NOT_INSTALLED",
    1432: "ERROR_INVALID_LB_MESSAGE",
    1433: "ERROR_SETCOUNT_ON_BAD_LB",
    1434: "ERROR_LB_WITHOUT_TABSTOPS",
    1435: "ERROR_DESTROY_OBJECT_OF_OTHER_THREAD",
    1436: "ERROR_CHILD_WINDOW_MENU",
    1437: "ERROR_NO_SYSTEM_MENU"
}

class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"          # Minor issues, operation can continue
    MEDIUM = "medium"    # Significant issues, may affect functionality
    HIGH = "high"        # Critical issues, operation should be retried
    CRITICAL = "critical" # Fatal errors, immediate attention required

class ErrorCategory(Enum):
    """Categories of errors for specialized handling."""
    WIN32_API = "win32_api"
    PERMISSION = "permission" 
    WINDOW_STATE = "window_state"
    SYSTEM_RESOURCE = "system_resource"
    APPLICATION_SPECIFIC = "application_specific"
    NETWORK = "network"
    HARDWARE = "hardware"
    UNKNOWN = "unknown"

class RecoveryStrategy(Enum):
    """Recovery strategies for different error types."""
    RETRY_IMMEDIATE = "retry_immediate"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    ROLLBACK = "rollback"
    ESCALATE_PRIVILEGES = "escalate_privileges"
    ALTERNATIVE_METHOD = "alternative_method"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    USER_INTERVENTION = "user_intervention"
    ABORT = "abort"

@dataclass
class ErrorInfo:
    """Comprehensive error information."""
    error_code: Optional[int] = None
    error_message: str = ""
    user_friendly_message: str = ""
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    category: ErrorCategory = ErrorCategory.UNKNOWN
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.RETRY_WITH_BACKOFF
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    traceback_str: str = ""
    suggested_actions: List[str] = field(default_factory=list)

@dataclass
class OperationContext:
    """Context information for operations that might need rollback."""
    operation_name: str
    target_hwnd: int
    original_state: Dict[str, Any] = field(default_factory=dict)
    rollback_actions: List[Callable] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_attempts: int = 3
    base_delay: float = 0.1
    max_delay: float = 5.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_errors: List[ErrorCategory] = field(default_factory=lambda: [
        ErrorCategory.WIN32_API, ErrorCategory.SYSTEM_RESOURCE
    ])

class WindowsErrorHandler:
    """
    Comprehensive error handling and recovery system for window operations.
    """
    
    def __init__(self, log_file: Optional[str] = None):
        """Initialize the error handler."""
        self.logger = self._setup_logging(log_file)
        self._error_stats: Dict[str, int] = {}
        self._operation_history: List[OperationContext] = []
        self._max_history = 100
        self._lock = threading.Lock()
        
        # Load error mappings
        self._win32_errors = WIN32_ERROR_CODES.copy()
        self._error_patterns = self._initialize_error_patterns()
        
        self.logger.info("WindowsErrorHandler initialized")
    
    def _setup_logging(self, log_file: Optional[str] = None) -> logging.Logger:
        """Setup comprehensive logging."""
        logger = logging.getLogger(f"{__name__}.{id(self)}")
        logger.setLevel(logging.DEBUG)
        
        # Avoid duplicate handlers
        if logger.handlers:
            return logger
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            try:
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)
                file_format = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
                )
                file_handler.setFormatter(file_format)
                logger.addHandler(file_handler)
            except Exception as e:
                logger.warning(f"Could not setup file logging: {e}")
        
        return logger
    
    def _initialize_error_patterns(self) -> Dict[str, ErrorInfo]:
        """Initialize common error patterns and their handling strategies."""
        patterns = {}
        
        # Win32 API errors
        patterns["invalid_window_handle"] = ErrorInfo(
            error_code=1400,
            error_message="Invalid window handle",
            user_friendly_message="The window is no longer available or has been closed",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.WIN32_API,
            recovery_strategy=RecoveryStrategy.GRACEFUL_DEGRADATION,
            suggested_actions=[
                "Refresh the window list",
                "Check if the application is still running",
                "Try the operation on a different window"
            ]
        )
        
        patterns["access_denied"] = ErrorInfo(
            error_code=5,
            error_message="Access denied",
            user_friendly_message="Insufficient permissions to manipulate this window",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.PERMISSION,
            recovery_strategy=RecoveryStrategy.ESCALATE_PRIVILEGES,
            suggested_actions=[
                "Run the application as administrator",
                "Check if the target application requires elevated privileges",
                "Try a less intrusive operation"
            ]
        )
        
        patterns["window_of_other_thread"] = ErrorInfo(
            error_code=1408,
            error_message="Window belongs to another thread",
            user_friendly_message="Cannot modify window from different thread context",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.WIN32_API,
            recovery_strategy=RecoveryStrategy.ALTERNATIVE_METHOD,
            suggested_actions=[
                "Use PostMessage instead of direct manipulation",
                "Try a delayed operation",
                "Use SendMessage with timeout"
            ]
        )
        
        return patterns
    
    def map_win32_error(self, error_code: int) -> ErrorInfo:
        """
        Map Win32 error code to comprehensive error information.
        
        Args:
            error_code: Win32 error code
            
        Returns:
            ErrorInfo with detailed information about the error
        """
        # Check for known patterns first
        for pattern_name, pattern_info in self._error_patterns.items():
            if pattern_info.error_code == error_code:
                return pattern_info
        
        # Generic mapping
        error_name = self._win32_errors.get(error_code, f"UNKNOWN_ERROR_{error_code}")
        
        # Determine severity and category based on error code
        severity = ErrorSeverity.MEDIUM
        category = ErrorCategory.WIN32_API
        recovery_strategy = RecoveryStrategy.RETRY_WITH_BACKOFF
        
        if error_code in [5, 1400, 1408]:  # Access denied, invalid handle, wrong thread
            severity = ErrorSeverity.HIGH
        elif error_code in [87, 1401, 1402]:  # Invalid parameter, handles
            severity = ErrorSeverity.MEDIUM
        elif error_code == 0:  # Success
            severity = ErrorSeverity.LOW
        
        # Permission-related errors
        if error_code in [5]:
            category = ErrorCategory.PERMISSION
            recovery_strategy = RecoveryStrategy.ESCALATE_PRIVILEGES
        
        return ErrorInfo(
            error_code=error_code,
            error_message=error_name,
            user_friendly_message=f"Windows API error: {error_name}",
            severity=severity,
            category=category,
            recovery_strategy=recovery_strategy,
            suggested_actions=[
                "Check if the operation is valid for this window type",
                "Verify window handle is still valid",
                "Try the operation again"
            ]
        )
    
    def analyze_exception(self, exception: Exception, context: Dict[str, Any] = None) -> ErrorInfo:
        """
        Analyze an exception and create comprehensive error information.
        
        Args:
            exception: The exception to analyze
            context: Additional context information
            
        Returns:
            ErrorInfo with analysis results
        """
        context = context or {}
        
        error_info = ErrorInfo(
            error_message=str(exception),
            context=context,
            traceback_str=traceback.format_exc()
        )
        
        # Analyze exception type
        exception_type = type(exception).__name__
        
        if "WindowsAPIError" in exception_type:
            error_info.category = ErrorCategory.WIN32_API
            # Try to extract error code from message
            try:
                if hasattr(exception, 'error_code'):
                    error_info.error_code = exception.error_code
                    mapped_error = self.map_win32_error(error_info.error_code)
                    error_info.user_friendly_message = mapped_error.user_friendly_message
                    error_info.recovery_strategy = mapped_error.recovery_strategy
                    error_info.suggested_actions = mapped_error.suggested_actions
            except:
                pass
        
        elif "PermissionError" in exception_type or "AccessDenied" in exception_type:
            error_info.category = ErrorCategory.PERMISSION
            error_info.severity = ErrorSeverity.HIGH
            error_info.recovery_strategy = RecoveryStrategy.ESCALATE_PRIVILEGES
            error_info.user_friendly_message = "Permission denied - administrator privileges may be required"
            error_info.suggested_actions = [
                "Run as administrator",
                "Check application permissions",
                "Try a different approach"
            ]
        
        elif "OSError" in exception_type or "WindowsError" in exception_type:
            error_info.category = ErrorCategory.SYSTEM_RESOURCE
            error_info.severity = ErrorSeverity.MEDIUM
            error_info.recovery_strategy = RecoveryStrategy.RETRY_WITH_BACKOFF
            error_info.user_friendly_message = "System resource error - operation may have failed temporarily"
        
        else:
            error_info.user_friendly_message = f"Unexpected error: {str(exception)}"
            error_info.recovery_strategy = RecoveryStrategy.RETRY_IMMEDIATE
        
        return error_info
    
    def record_operation_context(self, operation_name: str, hwnd: int, 
                               original_state: Dict[str, Any] = None) -> OperationContext:
        """
        Record operation context for potential rollback.
        
        Args:
            operation_name: Name of the operation
            hwnd: Target window handle
            original_state: Original state to restore on rollback
            
        Returns:
            OperationContext for tracking
        """
        context = OperationContext(
            operation_name=operation_name,
            target_hwnd=hwnd,
            original_state=original_state or {}
        )
        
        with self._lock:
            self._operation_history.append(context)
            # Keep history limited
            if len(self._operation_history) > self._max_history:
                self._operation_history.pop(0)
        
        self.logger.debug(f"Recorded operation context: {operation_name} on hwnd {hwnd}")
        return context
    
    def add_rollback_action(self, context: OperationContext, rollback_func: Callable):
        """Add a rollback action to operation context."""
        context.rollback_actions.append(rollback_func)
        self.logger.debug(f"Added rollback action for operation {context.operation_name}")
    
    def execute_rollback(self, context: OperationContext) -> bool:
        """
        Execute rollback actions for failed operation.
        
        Args:
            context: Operation context with rollback actions
            
        Returns:
            True if rollback successful, False otherwise
        """
        self.logger.info(f"Executing rollback for operation: {context.operation_name}")
        
        rollback_success = True
        
        # Execute rollback actions in reverse order
        for rollback_action in reversed(context.rollback_actions):
            try:
                rollback_action()
                self.logger.debug("Rollback action executed successfully")
            except Exception as e:
                self.logger.error(f"Rollback action failed: {e}")
                rollback_success = False
        
        return rollback_success
    
    def retry_with_backoff(self, func: Callable, config: RetryConfig = None, 
                          context: Dict[str, Any] = None) -> Any:
        """
        Execute function with retry logic and exponential backoff.
        
        Args:
            func: Function to execute
            config: Retry configuration
            context: Additional context for error analysis
            
        Returns:
            Function result if successful
            
        Raises:
            Last exception if all retries failed
        """
        config = config or RetryConfig()
        context = context or {}
        
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                result = func()
                if attempt > 0:
                    self.logger.info(f"Operation succeeded on attempt {attempt + 1}")
                return result
                
            except Exception as e:
                last_exception = e
                error_info = self.analyze_exception(e, context)
                
                # Check if we should retry this error
                if error_info.category not in config.retry_on_errors:
                    self.logger.warning(f"Error category {error_info.category.value} not retryable")
                    raise e
                
                if attempt < config.max_attempts - 1:
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    # Add jitter if enabled
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random() * 0.5)
                    
                    self.logger.warning(
                        f"Attempt {attempt + 1} failed: {error_info.error_message}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(f"All {config.max_attempts} attempts failed")
        
        # If we get here, all retries failed
        if last_exception:
            raise last_exception
    
    def handle_error(self, error: Union[Exception, int], context: Dict[str, Any] = None) -> ErrorInfo:
        """
        Comprehensive error handling with automatic recovery attempts.
        
        Args:
            error: Exception or Win32 error code
            context: Additional context information
            
        Returns:
            ErrorInfo with handling results
        """
        if isinstance(error, int):
            error_info = self.map_win32_error(error)
        else:
            error_info = self.analyze_exception(error, context)
        
        # Update error statistics
        error_key = f"{error_info.category.value}_{error_info.error_code or 'unknown'}"
        with self._lock:
            self._error_stats[error_key] = self._error_stats.get(error_key, 0) + 1
        
        # Log the error
        self.logger.error(
            f"Error handled: {error_info.error_message} "
            f"(Category: {error_info.category.value}, Severity: {error_info.severity.value})"
        )
        
        if error_info.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self.logger.error(f"Error traceback: {error_info.traceback_str}")
        
        return error_info
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics and analysis."""
        with self._lock:
            stats = {
                "total_errors": sum(self._error_stats.values()),
                "error_breakdown": self._error_stats.copy(),
                "recent_operations": len(self._operation_history),
                "most_common_errors": sorted(
                    self._error_stats.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:10]
            }
        
        return stats
    
    def save_error_report(self, filename: str = None):
        """Save comprehensive error report to file."""
        filename = filename or f"error_report_{int(time.time())}.json"
        
        report = {
            "timestamp": time.time(),
            "statistics": self.get_error_statistics(),
            "recent_operations": [
                {
                    "operation": op.operation_name,
                    "hwnd": op.target_hwnd,
                    "timestamp": op.timestamp,
                    "rollback_actions_count": len(op.rollback_actions)
                }
                for op in self._operation_history[-20:]  # Last 20 operations
            ]
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Error report saved to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save error report: {e}")

# Decorator for automatic error handling
def handle_errors(error_handler: WindowsErrorHandler = None, 
                 retry_config: RetryConfig = None,
                 rollback_on_error: bool = False):
    """
    Decorator for automatic error handling and recovery.
    
    Args:
        error_handler: Error handler instance
        retry_config: Retry configuration
        rollback_on_error: Whether to attempt rollback on error
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = error_handler or default_error_handler
            
            context = {
                "function": func.__name__,
                "args": str(args)[:200],  # Limit context size
                "kwargs": str(kwargs)[:200]
            }
            
            if retry_config:
                return handler.retry_with_backoff(
                    lambda: func(*args, **kwargs),
                    retry_config,
                    context
                )
            else:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_info = handler.handle_error(e, context)
                    # Re-raise with enhanced information
                    raise type(e)(f"{error_info.user_friendly_message}: {str(e)}")
        
        return wrapper
    return decorator

# Global error handler instance
default_error_handler = WindowsErrorHandler("window_operations.log")