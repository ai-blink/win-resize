"""
UWP Application Detection System
================================

Advanced detection and handling for Universal Windows Platform (UWP) applications.
UWP apps require special handling due to their containerized nature and different
window management behavior.

Key Features:
- UWP app identification using multiple heuristics
- Package information extraction
- App model ID resolution
- Store app metadata collection
"""

import os
import re
import winreg
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import logging

try:
    import wmi
    HAS_WMI = True
except ImportError:
    HAS_WMI = False

logger = logging.getLogger(__name__)

@dataclass
class UWPAppInfo:
    """Information about a UWP application."""
    package_name: str
    app_id: str
    display_name: str
    description: str
    publisher: str
    version: str
    install_location: str
    logo_path: str
    is_framework: bool = False
    is_system_app: bool = False

class UWPDetector:
    """
    Detects and provides information about UWP applications.
    
    Uses multiple detection methods including:
    - Window class name analysis
    - Process command line inspection
    - Windows Registry queries
    - WMI queries (if available)
    """
    
    # Known UWP window classes
    UWP_WINDOW_CLASSES = {
        'ApplicationFrameWindow',
        'Windows.UI.Core.CoreWindow',
        'WinUIDesktopWin32WindowClass',
        'ApplicationManager_DesktopShellWindow'
    }
    
    # UWP process patterns
    UWP_PROCESS_PATTERNS = [
        r'.*\\WindowsApps\\.*',
        r'.*\\Microsoft\..*',
        r'.*\\.*_.*_.*_.*_.*\\.*'  # Package naming pattern
    ]
    
    # System UWP apps to filter out
    SYSTEM_UWP_APPS = {
        'Microsoft.Windows.Cortana',
        'Microsoft.Windows.StartMenuExperienceHost',
        'Microsoft.Windows.ShellExperienceHost',
        'Microsoft.AAD.BrokerPlugin',
        'Microsoft.AccountsControl',
        'Microsoft.AsyncTextService',
        'Microsoft.BioEnrollment',
        'Microsoft.CredDialogHost',
        'Microsoft.ECApp',
        'Microsoft.LockApp',
        'Microsoft.MicrosoftEdgeDevToolsClient',
        'Microsoft.Win32WebViewHost',
        'Microsoft.Windows.AssignedAccessLockApp',
        'Microsoft.Windows.CallingShellApp',
        'Microsoft.Windows.CloudExperienceHost',
        'Microsoft.Windows.ContentDeliveryManager',
        'Microsoft.Windows.Cortana',
        'Microsoft.Windows.NarratorQuickStart',
        'Microsoft.Windows.OOBENetworkConnectionFlow',
        'Microsoft.Windows.OOBENetworkCaptivePortal',
        'Microsoft.Windows.ParentalControls',
        'Microsoft.Windows.PeopleExperienceHost',
        'Microsoft.Windows.PinningConfirmationDialog',
        'Microsoft.Windows.SecHealthUI',
        'Microsoft.Windows.SecureAssessmentBrowser',
        'Microsoft.Windows.StartMenuExperienceHost',
        'Microsoft.Windows.XGpuEjectDialog',
        'Microsoft.XboxGameCallableUI'
    }
    
    def __init__(self):
        """Initialize the UWP detector."""
        self._app_cache: Dict[str, UWPAppInfo] = {}
        self._cache_populated = False
        
        # Initialize WMI if available
        self._wmi_service = None
        if HAS_WMI:
            try:
                self._wmi_service = wmi.WMI()
            except Exception as e:
                logger.debug(f"Could not initialize WMI: {e}")
        
        logger.debug("UWP detector initialized")
    
    def is_uwp_window_class(self, class_name: str) -> bool:
        """Check if a window class indicates a UWP app."""
        return class_name in self.UWP_WINDOW_CLASSES
    
    def is_uwp_process_path(self, exe_path: str) -> bool:
        """Check if a process path indicates a UWP app."""
        if not exe_path:
            return False
        
        exe_path_lower = exe_path.lower()
        
        # Check for WindowsApps folder
        if 'windowsapps' in exe_path_lower:
            return True
        
        # Check patterns
        for pattern in self.UWP_PROCESS_PATTERNS:
            if re.match(pattern, exe_path, re.IGNORECASE):
                return True
        
        return False
    
    def extract_package_name_from_path(self, exe_path: str) -> Optional[str]:
        """Extract UWP package name from executable path."""
        if not exe_path:
            return None
        
        # Pattern: ...\\WindowsApps\\PackageName_version_arch_hash\\...
        match = re.search(r'WindowsApps\\([^\\]+)\\', exe_path, re.IGNORECASE)
        if match:
            full_package = match.group(1)
            # Remove version, architecture, and hash suffixes
            package_parts = full_package.split('_')
            if len(package_parts) >= 1:
                return package_parts[0]
        
        return None
    
    def get_uwp_app_info(self, package_name: str) -> Optional[UWPAppInfo]:
        """Get detailed information about a UWP app."""
        if not package_name:
            return None
        
        # Check cache first
        if package_name in self._app_cache:
            return self._app_cache[package_name]
        
        # Try to get info from registry
        app_info = self._get_app_info_from_registry(package_name)
        if app_info:
            self._app_cache[package_name] = app_info
            return app_info
        
        # Try WMI if available
        if self._wmi_service:
            app_info = self._get_app_info_from_wmi(package_name)
            if app_info:
                self._app_cache[package_name] = app_info
                return app_info
        
        return None
    
    def _get_app_info_from_registry(self, package_name: str) -> Optional[UWPAppInfo]:
        """Get UWP app information from Windows Registry."""
        try:
            # Try different registry locations
            registry_paths = [
                r'SOFTWARE\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages',
                r'SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\Applications'
            ]
            
            for registry_path in registry_paths:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                        # Enumerate subkeys to find matching package
                        i = 0
                        while True:
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                if package_name.lower() in subkey_name.lower():
                                    return self._extract_app_info_from_registry_key(registry_path, subkey_name)
                                i += 1
                            except WindowsError:
                                break
                except FileNotFoundError:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error reading registry for UWP app {package_name}: {e}")
        
        return None
    
    def _extract_app_info_from_registry_key(self, registry_path: str, subkey_name: str) -> Optional[UWPAppInfo]:
        """Extract app info from a specific registry key."""
        try:
            full_path = f"{registry_path}\\{subkey_name}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, full_path) as subkey:
                
                # Try to read common values
                display_name = self._read_registry_value(subkey, "DisplayName", subkey_name)
                description = self._read_registry_value(subkey, "Description", "")
                publisher = self._read_registry_value(subkey, "Publisher", "")
                version = self._read_registry_value(subkey, "Version", "")
                install_location = self._read_registry_value(subkey, "InstallLocation", "")
                
                # Extract package name from subkey name
                package_parts = subkey_name.split('_')
                package_name = package_parts[0] if package_parts else subkey_name
                
                return UWPAppInfo(
                    package_name=package_name,
                    app_id=subkey_name,
                    display_name=display_name,
                    description=description,
                    publisher=publisher,
                    version=version,
                    install_location=install_location,
                    logo_path="",
                    is_system_app=package_name in self.SYSTEM_UWP_APPS
                )
                
        except Exception as e:
            logger.debug(f"Error extracting from registry key {subkey_name}: {e}")
        
        return None
    
    def _read_registry_value(self, key, value_name: str, default: str = "") -> str:
        """Safely read a registry value."""
        try:
            value, _ = winreg.QueryValueEx(key, value_name)
            return str(value)
        except FileNotFoundError:
            return default
        except Exception:
            return default
    
    def _get_app_info_from_wmi(self, package_name: str) -> Optional[UWPAppInfo]:
        """Get UWP app information using WMI (if available)."""
        if not self._wmi_service:
            return None
        
        try:
            # Query Win32_Process for UWP processes
            for process in self._wmi_service.Win32_Process():
                if process.ExecutablePath and 'windowsapps' in process.ExecutablePath.lower():
                    extracted_package = self.extract_package_name_from_path(process.ExecutablePath)
                    if extracted_package and package_name.lower() in extracted_package.lower():
                        return UWPAppInfo(
                            package_name=extracted_package,
                            app_id=process.ProcessId,
                            display_name=extracted_package,
                            description="",
                            publisher="",
                            version="",
                            install_location=os.path.dirname(process.ExecutablePath),
                            logo_path="",
                            is_system_app=extracted_package in self.SYSTEM_UWP_APPS
                        )
        except Exception as e:
            logger.debug(f"Error using WMI to get UWP app info: {e}")
        
        return None
    
    def is_system_uwp_app(self, package_name: str) -> bool:
        """Check if a UWP app is a system app that should be filtered out."""
        return package_name in self.SYSTEM_UWP_APPS
    
    def populate_app_cache(self):
        """Pre-populate the app cache with known UWP applications."""
        if self._cache_populated:
            return
        
        try:
            # Get all installed UWP packages from registry
            registry_path = r'SOFTWARE\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages'
            
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        app_info = self._extract_app_info_from_registry_key(registry_path, subkey_name)
                        if app_info:
                            self._app_cache[app_info.package_name] = app_info
                        i += 1
                    except WindowsError:
                        break
            
            self._cache_populated = True
            logger.info(f"Populated UWP app cache with {len(self._app_cache)} applications")
            
        except Exception as e:
            logger.debug(f"Error populating UWP app cache: {e}")
    
    def get_all_uwp_apps(self) -> List[UWPAppInfo]:
        """Get information about all installed UWP applications."""
        if not self._cache_populated:
            self.populate_app_cache()
        
        return list(self._app_cache.values())
    
    def get_user_uwp_apps(self) -> List[UWPAppInfo]:
        """Get only user-installed UWP applications (excluding system apps)."""
        all_apps = self.get_all_uwp_apps()
        return [app for app in all_apps if not app.is_system_app]

# Default instance
default_uwp_detector = UWPDetector()

# Convenience functions
def is_uwp_window_class(class_name: str) -> bool:
    """Check if window class indicates UWP app using default detector."""
    return default_uwp_detector.is_uwp_window_class(class_name)

def is_uwp_process_path(exe_path: str) -> bool:
    """Check if process path indicates UWP app using default detector."""
    return default_uwp_detector.is_uwp_process_path(exe_path)

def get_uwp_app_info(package_name: str) -> Optional[UWPAppInfo]:
    """Get UWP app info using default detector."""
    return default_uwp_detector.get_uwp_app_info(package_name)