"""
Privilege and Permission Handler
===============================

Handles elevated permissions, UAC requirements, and security constraints
for window manipulation operations that require special privileges.

Key Features:
- UAC elevation detection and handling
- Administrator privilege checks
- Security-sensitive application detection
- Permission escalation for restricted operations
- Safe fallback mechanisms
"""

import ctypes
import ctypes.wintypes
import os
import sys
import subprocess
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class PrivilegeLevel(Enum):
    """Different privilege levels for operations."""
    USER = "user"                    # Normal user privileges
    ELEVATED = "elevated"           # Elevated user (UAC)
    ADMINISTRATOR = "administrator" # Full administrator
    SYSTEM = "system"              # System level access

class PermissionResult(Enum):
    """Results of permission checks."""
    GRANTED = "granted"
    DENIED = "denied"
    REQUIRES_ELEVATION = "requires_elevation"
    BLOCKED_BY_SECURITY = "blocked_by_security"

@dataclass
class PrivilegeInfo:
    """Information about current privilege level and capabilities."""
    current_level: PrivilegeLevel
    is_admin: bool
    is_elevated: bool
    can_elevate: bool
    restricted_processes: List[str]
    capabilities: Dict[str, bool]

class PrivilegeHandler:
    """
    Handles privilege management and elevation for window operations.
    """
    
    def __init__(self):
        """Initialize the privilege handler."""
        self._privilege_info: Optional[PrivilegeInfo] = None
        self._security_restricted_processes = {
            # Anti-cheat software
            'battleye.exe', 'easyanticheat.exe', 'vanguard.exe',
            'faceitac.exe', 'esea.exe', 'cevo.exe',
            
            # System security
            'csrss.exe', 'winlogon.exe', 'lsass.exe', 'services.exe',
            'smss.exe', 'wininit.exe', 'dwm.exe',
            
            # Windows Defender and security
            'msmpeng.exe', 'antimalware.exe', 'windefend.exe',
            
            # Secure applications
            'keepass.exe', 'bitwarden.exe', 'lastpass.exe',
        }
        
        logger.debug("Privilege handler initialized")
    
    def get_privilege_info(self) -> PrivilegeInfo:
        """
        Get current privilege information.
        
        Returns:
            PrivilegeInfo with current privilege status
        """
        if self._privilege_info is None:
            self._privilege_info = self._analyze_privileges()
        
        return self._privilege_info
    
    def _analyze_privileges(self) -> PrivilegeInfo:
        """Analyze current process privileges."""
        try:
            # Check if running as administrator
            is_admin = self._check_admin_privileges()
            
            # Check if process is elevated
            is_elevated = self._check_elevation_status()
            
            # Determine current privilege level
            if is_admin and is_elevated:
                current_level = PrivilegeLevel.ADMINISTRATOR
            elif is_elevated:
                current_level = PrivilegeLevel.ELEVATED
            else:
                current_level = PrivilegeLevel.USER
            
            # Check elevation capability
            can_elevate = self._can_request_elevation()
            
            # Build capabilities
            capabilities = {
                'manipulate_user_windows': True,
                'manipulate_elevated_windows': is_elevated,
                'manipulate_system_windows': is_admin,
                'modify_protected_processes': is_admin,
                'access_secure_desktop': is_admin,
                'bypass_uipi': is_elevated,  # User Interface Privilege Isolation
            }
            
            return PrivilegeInfo(
                current_level=current_level,
                is_admin=is_admin,
                is_elevated=is_elevated,
                can_elevate=can_elevate,
                restricted_processes=list(self._security_restricted_processes),
                capabilities=capabilities
            )
            
        except Exception as e:
            logger.error(f"Error analyzing privileges: {e}")
            
            # Return safe defaults
            return PrivilegeInfo(
                current_level=PrivilegeLevel.USER,
                is_admin=False,
                is_elevated=False,
                can_elevate=False,
                restricted_processes=list(self._security_restricted_processes),
                capabilities={'manipulate_user_windows': True}
            )
    
    def _check_admin_privileges(self) -> bool:
        """Check if running with administrator privileges."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    
    def _check_elevation_status(self) -> bool:
        """Check if process is running elevated (UAC)."""
        try:
            # Get current process token
            TOKEN_QUERY = 0x0008
            TokenElevation = 20
            
            process = ctypes.windll.kernel32.GetCurrentProcess()
            token = ctypes.wintypes.HANDLE()
            
            if not ctypes.windll.advapi32.OpenProcessToken(process, TOKEN_QUERY, ctypes.byref(token)):
                return False
            
            elevation = ctypes.wintypes.DWORD()
            size = ctypes.wintypes.DWORD()
            
            result = ctypes.windll.advapi32.GetTokenInformation(
                token, TokenElevation, ctypes.byref(elevation),
                ctypes.sizeof(elevation), ctypes.byref(size)
            )
            
            ctypes.windll.kernel32.CloseHandle(token)
            
            return bool(result and elevation.value)
            
        except Exception as e:
            logger.debug(f"Error checking elevation status: {e}")
            return False
    
    def _can_request_elevation(self) -> bool:
        """Check if elevation can be requested."""
        try:
            # On Windows Vista+, UAC allows elevation requests
            version = sys.getwindowsversion()
            return version.major >= 6
        except Exception:
            return False
    
    def check_window_access_permission(self, hwnd: int, process_name: str = None) -> PermissionResult:
        """
        Check if we have permission to manipulate a specific window.
        
        Args:
            hwnd: Window handle
            process_name: Optional process name for additional checks
            
        Returns:
            PermissionResult indicating access level
        """
        try:
            privilege_info = self.get_privilege_info()
            
            # Check if process is security-restricted
            if process_name and process_name.lower() in self._security_restricted_processes:
                if not privilege_info.is_admin:
                    return PermissionResult.BLOCKED_BY_SECURITY
            
            # Try to get basic window information (low privilege operation)
            try:
                title_length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if title_length < 0:
                    return PermissionResult.DENIED
            except Exception:
                return PermissionResult.DENIED
            
            # Check if window belongs to elevated process
            if self._is_window_elevated(hwnd):
                if not privilege_info.is_elevated:
                    return PermissionResult.REQUIRES_ELEVATION
            
            return PermissionResult.GRANTED
            
        except Exception as e:
            logger.debug(f"Error checking window access permission: {e}")
            return PermissionResult.DENIED
    
    def _is_window_elevated(self, hwnd: int) -> bool:
        """Check if a window belongs to an elevated process."""
        try:
            # Get process ID
            process_id = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            
            if not process_id.value:
                return False
            
            # Open process handle
            PROCESS_QUERY_INFORMATION = 0x0400
            process_handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION, False, process_id.value
            )
            
            if not process_handle:
                return False
            
            try:
                # Get process token
                TOKEN_QUERY = 0x0008
                token = ctypes.wintypes.HANDLE()
                
                if not ctypes.windll.advapi32.OpenProcessToken(
                    process_handle, TOKEN_QUERY, ctypes.byref(token)
                ):
                    return False
                
                try:
                    # Check elevation
                    TokenElevation = 20
                    elevation = ctypes.wintypes.DWORD()
                    size = ctypes.wintypes.DWORD()
                    
                    result = ctypes.windll.advapi32.GetTokenInformation(
                        token, TokenElevation, ctypes.byref(elevation),
                        ctypes.sizeof(elevation), ctypes.byref(size)
                    )
                    
                    return bool(result and elevation.value)
                    
                finally:
                    ctypes.windll.kernel32.CloseHandle(token)
                    
            finally:
                ctypes.windll.kernel32.CloseHandle(process_handle)
                
        except Exception as e:
            logger.debug(f"Error checking if window is elevated: {e}")
            return False
    
    def request_elevation_if_needed(self, operation_description: str = "window manipulation") -> bool:
        """
        Request elevation if needed for the operation.
        
        Args:
            operation_description: Description of the operation requiring elevation
            
        Returns:
            True if elevation was successful or not needed
        """
        privilege_info = self.get_privilege_info()
        
        if privilege_info.is_elevated:
            return True  # Already elevated
        
        if not privilege_info.can_elevate:
            logger.warning("Cannot request elevation on this system")
            return False
        
        try:
            # Get current script path
            script_path = os.path.abspath(sys.argv[0])
            
            # Request elevation via UAC
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script_path}"', None, 1
            )
            
            # ShellExecuteW returns > 32 on success
            if result > 32:
                logger.info(f"Elevation requested for {operation_description}")
                return True
            else:
                logger.warning(f"Elevation request failed: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error requesting elevation: {e}")
            return False
    
    def get_safe_operation_recommendations(self, target_windows: List[int]) -> Dict[int, str]:
        """
        Get recommendations for safe operations on target windows.
        
        Args:
            target_windows: List of window handles
            
        Returns:
            Dictionary mapping window handles to recommendation strings
        """
        recommendations = {}
        
        for hwnd in target_windows:
            try:
                # Check permission level
                permission = self.check_window_access_permission(hwnd)
                
                if permission == PermissionResult.GRANTED:
                    recommendations[hwnd] = "Full manipulation available"
                elif permission == PermissionResult.REQUIRES_ELEVATION:
                    recommendations[hwnd] = "Requires elevation - run as administrator"
                elif permission == PermissionResult.BLOCKED_BY_SECURITY:
                    recommendations[hwnd] = "Blocked by security software - operation not recommended"
                else:
                    recommendations[hwnd] = "Access denied - check window validity"
                    
            except Exception as e:
                recommendations[hwnd] = f"Error checking permissions: {e}"
        
        return recommendations
    
    def create_security_report(self) -> Dict[str, any]:
        """
        Create a security and privilege report.
        
        Returns:
            Dictionary with security information
        """
        privilege_info = self.get_privilege_info()
        
        return {
            'privilege_level': privilege_info.current_level.value,
            'is_administrator': privilege_info.is_admin,
            'is_elevated': privilege_info.is_elevated,
            'can_request_elevation': privilege_info.can_elevate,
            'capabilities': privilege_info.capabilities,
            'restricted_processes_count': len(privilege_info.restricted_processes),
            'security_recommendations': [
                "Run as administrator for full window manipulation capabilities" if not privilege_info.is_admin else "Administrator privileges detected",
                "Some security software may block window manipulation",
                "System windows require elevated privileges",
                "UWP applications may have additional restrictions"
            ]
        }

# Default instance
default_privilege_handler = PrivilegeHandler()

# Convenience functions
def check_admin_privileges() -> bool:
    """Check if running with admin privileges using default handler."""
    return default_privilege_handler.get_privilege_info().is_admin

def check_window_permission(hwnd: int, process_name: str = None) -> PermissionResult:
    """Check window manipulation permission using default handler."""
    return default_privilege_handler.check_window_access_permission(hwnd, process_name)

def get_security_report() -> Dict[str, any]:
    """Get security report using default handler."""
    return default_privilege_handler.create_security_report()