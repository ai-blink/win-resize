"""
Privilege and UAC Error Handling Extension
=========================================

Extended error handling specifically for privilege escalation,
UAC requirements, and security-related window manipulation errors.

Key Features:
- UAC elevation request handling
- Administrator privilege detection
- Security constraint error recovery
- Privilege-based operation fallbacks
- Safe mode operations for restricted environments
"""

import os
import sys
import subprocess
import ctypes
import ctypes.wintypes
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from .error_handler import (
    WindowsErrorHandler, ErrorInfo, ErrorSeverity, ErrorCategory, 
    RecoveryStrategy, OperationContext
)
from .privilege_handler import PrivilegeHandler, PrivilegeLevel, PermissionResult

logger = logging.getLogger(__name__)

class PrivilegeErrorType(Enum):
    """Specific privilege-related error types."""
    REQUIRES_ELEVATION = "requires_elevation"
    REQUIRES_ADMIN = "requires_admin"
    BLOCKED_BY_UAC = "blocked_by_uac"
    BLOCKED_BY_SECURITY = "blocked_by_security"
    INSUFFICIENT_RIGHTS = "insufficient_rights"
    PROCESS_PROTECTED = "process_protected"

@dataclass
class PrivilegeErrorInfo(ErrorInfo):
    """Extended error info for privilege-related errors."""
    required_privilege: PrivilegeLevel = PrivilegeLevel.USER
    current_privilege: PrivilegeLevel = PrivilegeLevel.USER
    can_elevate: bool = False
    elevation_method: Optional[str] = None
    safe_alternatives: List[str] = None

class PrivilegeErrorHandler(WindowsErrorHandler):
    """
    Extended error handler for privilege and security-related errors.
    """
    
    def __init__(self, log_file: Optional[str] = None):
        """Initialize privilege error handler."""
        super().__init__(log_file)
        self.privilege_handler = PrivilegeHandler()
        self._safe_mode_enabled = False
        self._elevation_requested = False
        
        # Initialize privilege-specific error patterns
        self._init_privilege_patterns()
        
        logger.info("PrivilegeErrorHandler initialized")
    
    def _init_privilege_patterns(self):
        """Initialize privilege-specific error patterns."""
        # UAC elevation required
        self._error_patterns["uac_elevation_required"] = PrivilegeErrorInfo(
            error_code=5,  # ACCESS_DENIED
            error_message="UAC elevation required",
            user_friendly_message="This operation requires administrator privileges",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.PERMISSION,
            recovery_strategy=RecoveryStrategy.ESCALATE_PRIVILEGES,
            required_privilege=PrivilegeLevel.ELEVATED,
            elevation_method="uac_prompt",
            suggested_actions=[
                "Right-click and select 'Run as administrator'",
                "Enable UAC elevation in settings",
                "Contact system administrator for permissions"
            ],
            safe_alternatives=[
                "Try basic window information queries only",
                "Use limited manipulation mode",
                "Switch to read-only operations"
            ]
        )
        
        # Security software blocking
        self._error_patterns["security_software_block"] = PrivilegeErrorInfo(
            error_message="Blocked by security software",
            user_friendly_message="Anti-virus or security software is blocking this operation",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.APPLICATION_SPECIFIC,
            recovery_strategy=RecoveryStrategy.GRACEFUL_DEGRADATION,
            suggested_actions=[
                "Check security software settings",
                "Add application to whitelist",
                "Temporarily disable real-time protection"
            ],
            safe_alternatives=[
                "Use passive window monitoring",
                "Switch to information-only mode",
                "Try alternative manipulation methods"
            ]
        )
        
        # Protected process
        self._error_patterns["protected_process"] = PrivilegeErrorInfo(
            error_message="Protected process access denied",
            user_friendly_message="Cannot manipulate windows of protected system processes",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.PERMISSION,
            recovery_strategy=RecoveryStrategy.GRACEFUL_DEGRADATION,
            required_privilege=PrivilegeLevel.SYSTEM,
            suggested_actions=[
                "Skip protected system processes",
                "Use alternative detection methods",
                "Focus on user applications only"
            ],
            safe_alternatives=[
                "Read-only process information",
                "Basic window enumeration only",
                "Skip manipulation attempts"
            ]
        )
    
    def check_privilege_requirements(self, operation: str, hwnd: int) -> PrivilegeErrorInfo:
        """
        Check privilege requirements for a specific operation.
        
        Args:
            operation: Operation name
            hwnd: Target window handle
            
        Returns:
            PrivilegeErrorInfo with requirements analysis
        """
        current_info = self.privilege_handler.get_privilege_info()
        permission_result = self.privilege_handler.check_window_access_permission(hwnd)
        
        error_info = PrivilegeErrorInfo(
            current_privilege=current_info.current_level,
            can_elevate=current_info.can_elevate
        )
        
        # Analyze permission requirements
        if permission_result == PermissionResult.GRANTED:
            error_info.severity = ErrorSeverity.LOW
            error_info.user_friendly_message = "Operation should succeed with current privileges"
            error_info.recovery_strategy = RecoveryStrategy.RETRY_IMMEDIATE
            
        elif permission_result == PermissionResult.REQUIRES_ELEVATION:
            error_info.required_privilege = PrivilegeLevel.ELEVATED
            error_info.severity = ErrorSeverity.HIGH
            error_info.category = ErrorCategory.PERMISSION
            error_info.user_friendly_message = "Operation requires UAC elevation"
            error_info.recovery_strategy = RecoveryStrategy.ESCALATE_PRIVILEGES
            error_info.elevation_method = "uac_prompt"
            
        elif permission_result == PermissionResult.BLOCKED_BY_SECURITY:
            error_info.severity = ErrorSeverity.HIGH
            error_info.category = ErrorCategory.APPLICATION_SPECIFIC
            error_info.user_friendly_message = "Operation blocked by security software"
            error_info.recovery_strategy = RecoveryStrategy.GRACEFUL_DEGRADATION
            
        else:  # DENIED
            error_info.severity = ErrorSeverity.MEDIUM
            error_info.user_friendly_message = "Operation not permitted for this window"
            error_info.recovery_strategy = RecoveryStrategy.GRACEFUL_DEGRADATION
        
        return error_info
    
    def request_elevation(self, operation_description: str = "window manipulation") -> bool:
        """
        Request UAC elevation for privileged operations.
        
        Args:
            operation_description: Description of operation requiring elevation
            
        Returns:
            True if elevation successful or already elevated
        """
        if self._elevation_requested:
            logger.debug("Elevation already requested in this session")
            return False
        
        privilege_info = self.privilege_handler.get_privilege_info()
        
        if privilege_info.is_elevated:
            logger.debug("Already running with elevated privileges")
            return True
        
        if not privilege_info.can_elevate:
            logger.warning("Cannot request elevation on this system")
            return False
        
        try:
            logger.info(f"Requesting UAC elevation for: {operation_description}")
            
            # Get current script path
            script_path = os.path.abspath(sys.argv[0])
            
            # Build elevation command
            elevation_args = [
                sys.executable,
                script_path,
                "--elevated",
                f"--operation={operation_description}"
            ]
            
            # Request elevation using ShellExecute with 'runas'
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                sys.executable,
                " ".join(f'"{arg}"' for arg in elevation_args[1:]),
                None,
                1  # SW_SHOWNORMAL
            )
            
            self._elevation_requested = True
            
            # ShellExecuteW returns > 32 on success
            if result > 32:
                logger.info("UAC elevation request successful")
                return True
            else:
                logger.warning(f"UAC elevation request failed with code: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error requesting elevation: {e}")
            return False
    
    def enable_safe_mode(self):
        """Enable safe mode - only non-intrusive operations allowed."""
        self._safe_mode_enabled = True
        logger.info("Safe mode enabled - restricting to read-only operations")
    
    def disable_safe_mode(self):
        """Disable safe mode - allow all operations based on privileges."""
        self._safe_mode_enabled = False
        logger.info("Safe mode disabled")
    
    def is_safe_mode_enabled(self) -> bool:
        """Check if safe mode is enabled."""
        return self._safe_mode_enabled
    
    def get_safe_alternatives(self, operation: str, hwnd: int) -> List[str]:
        """
        Get safe alternative operations when privileged operation fails.
        
        Args:
            operation: Failed operation name
            hwnd: Target window handle
            
        Returns:
            List of safe alternative operations
        """
        alternatives = []
        
        if operation in ["move_window", "resize_window"]:
            alternatives.extend([
                "get_window_info",
                "monitor_window_changes",
                "record_window_state"
            ])
        
        elif operation in ["set_topmost", "bring_to_front"]:
            alternatives.extend([
                "enumerate_z_order",
                "get_window_hierarchy",
                "track_focus_changes"
            ])
        
        elif operation in ["minimize", "maximize", "restore"]:
            alternatives.extend([
                "get_window_state",
                "monitor_state_changes",
                "log_state_transitions"
            ])
        
        # Always available safe operations
        alternatives.extend([
            "get_window_title",
            "get_window_class",
            "get_window_process_info",
            "check_window_visibility"
        ])
        
        return alternatives
    
    def handle_privilege_error(self, error: Exception, operation: str, 
                             hwnd: int, context: Dict[str, Any] = None) -> PrivilegeErrorInfo:
        """
        Handle privilege-related errors with specialized recovery.
        
        Args:
            error: The privilege-related error
            operation: Operation that failed
            hwnd: Target window handle
            context: Additional context
            
        Returns:
            PrivilegeErrorInfo with handling results
        """
        context = context or {}
        context.update({
            "operation": operation,
            "hwnd": hwnd,
            "safe_mode": self._safe_mode_enabled
        })
        
        # Start with base error analysis
        error_info = self.analyze_exception(error, context)
        
        # Convert to PrivilegeErrorInfo
        privilege_error = PrivilegeErrorInfo(
            error_code=error_info.error_code,
            error_message=error_info.error_message,
            user_friendly_message=error_info.user_friendly_message,
            severity=error_info.severity,
            category=error_info.category,
            recovery_strategy=error_info.recovery_strategy,
            context=error_info.context,
            timestamp=error_info.timestamp,
            traceback_str=error_info.traceback_str,
            suggested_actions=error_info.suggested_actions
        )
        
        # Add privilege-specific analysis
        privilege_requirements = self.check_privilege_requirements(operation, hwnd)
        privilege_error.required_privilege = privilege_requirements.required_privilege
        privilege_error.current_privilege = privilege_requirements.current_privilege
        privilege_error.can_elevate = privilege_requirements.can_elevate
        privilege_error.elevation_method = privilege_requirements.elevation_method
        
        # Get safe alternatives
        privilege_error.safe_alternatives = self.get_safe_alternatives(operation, hwnd)
        
        # Enhance error message with privilege context
        if privilege_error.recovery_strategy == RecoveryStrategy.ESCALATE_PRIVILEGES:
            if privilege_error.can_elevate:
                privilege_error.user_friendly_message += " (Elevation available - run as administrator)"
            else:
                privilege_error.user_friendly_message += " (Elevation not available on this system)"
        
        # Log privilege-specific information
        logger.error(
            f"Privilege error in {operation}: {privilege_error.error_message} "
            f"(Required: {privilege_error.required_privilege.value}, "
            f"Current: {privilege_error.current_privilege.value})"
        )
        
        return privilege_error
    
    def execute_with_privilege_handling(self, func: Callable, operation: str, 
                                      hwnd: int, allow_elevation: bool = True) -> Any:
        """
        Execute function with comprehensive privilege error handling.
        
        Args:
            func: Function to execute
            operation: Operation name for logging
            hwnd: Target window handle
            allow_elevation: Whether to allow elevation requests
            
        Returns:
            Function result if successful
            
        Raises:
            Enhanced exception with privilege information
        """
        # Check privileges before attempting operation
        privilege_check = self.check_privilege_requirements(operation, hwnd)
        
        if privilege_check.severity == ErrorSeverity.HIGH and allow_elevation:
            if privilege_check.can_elevate and not self._elevation_requested:
                logger.info(f"Operation {operation} may require elevation")
                # Don't automatically elevate, just warn
        
        try:
            return func()
            
        except Exception as e:
            privilege_error = self.handle_privilege_error(e, operation, hwnd)
            
            # Try recovery strategies
            if privilege_error.recovery_strategy == RecoveryStrategy.ESCALATE_PRIVILEGES and allow_elevation:
                if not self._elevation_requested and privilege_error.can_elevate:
                    logger.info(f"Attempting elevation for failed operation: {operation}")
                    if self.request_elevation(f"{operation} on window {hwnd}"):
                        # Elevation requested - the elevated process will handle the operation
                        raise PrivilegeElevationRequested(
                            f"Elevation requested for {operation}. "
                            f"Operation will be handled by elevated process."
                        )
            
            elif privilege_error.recovery_strategy == RecoveryStrategy.GRACEFUL_DEGRADATION:
                logger.info(f"Using graceful degradation for {operation}")
                if self._safe_mode_enabled:
                    raise SafeModeRestriction(
                        f"Operation {operation} not allowed in safe mode. "
                        f"Safe alternatives: {', '.join(privilege_error.safe_alternatives)}"
                    )
            
            # Re-raise with enhanced information
            raise PrivilegeError(
                f"{privilege_error.user_friendly_message}: {str(e)}"
            ) from e

# Custom exceptions for privilege handling
class PrivilegeError(Exception):
    """Base exception for privilege-related errors."""
    pass

class PrivilegeElevationRequested(PrivilegeError):
    """Exception raised when elevation is requested."""
    pass

class SafeModeRestriction(PrivilegeError):
    """Exception raised when operation is blocked by safe mode."""
    pass

# Global privilege error handler
default_privilege_error_handler = PrivilegeErrorHandler("privilege_errors.log")