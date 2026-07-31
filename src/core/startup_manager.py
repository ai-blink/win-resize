"""
Windows Startup Integration Manager
===================================

Manages Windows startup integration for automatic service launch.
Provides registry-based startup registration and service installation.

Key Features:
- Windows Registry startup program registration
- User-level and system-level installation options
- UAC privilege handling
- Safe registry operations with backup
- Automatic service re-registration on updates
- Clean uninstall functionality
- Boot performance optimization
"""

import sys
import os
import winreg
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
import subprocess
import tempfile
import shutil

logger = logging.getLogger(__name__)

@dataclass
class StartupConfig:
    """Configuration for startup integration."""
    app_name: str = "WindowResizer"
    display_name: str = "WindowResizer Background Service"
    description: str = "Automatically applies window profiles and monitors processes"
    executable_path: str = ""
    arguments: str = "--tray --autostart"
    user_level: bool = True  # True for user-level, False for system-level
    enabled: bool = True
    start_minimized: bool = True

class StartupManager:
    """Manages Windows startup integration."""
    
    # Registry paths
    USER_STARTUP_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    SYSTEM_STARTUP_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    STARTUP_APPROVED_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
    
    def __init__(self, config: StartupConfig = None):
        """Initialize startup manager."""
        self.config = config or StartupConfig()
        
        # Set executable path if not provided
        if not self.config.executable_path:
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                self.config.executable_path = sys.executable
            else:
                # Running as Python script
                script_path = Path(__file__).parent.parent.parent / "main.py"
                self.config.executable_path = f'"{sys.executable}" "{script_path}"'
        
        logger.info("StartupManager initialized")
    
    def is_startup_enabled(self) -> bool:
        """Check if startup is currently enabled."""
        try:
            if self.config.user_level:
                key = winreg.HKEY_CURRENT_USER
                subkey = self.USER_STARTUP_KEY
            else:
                key = winreg.HKEY_LOCAL_MACHINE
                subkey = self.SYSTEM_STARTUP_KEY
            
            with winreg.OpenKey(key, subkey, 0, winreg.KEY_READ) as reg_key:
                try:
                    value, _ = winreg.QueryValueEx(reg_key, self.config.app_name)
                    return True
                except FileNotFoundError:
                    return False
                    
        except Exception as e:
            logger.error(f"Error checking startup status: {e}")
            return False
    
    def enable_startup(self) -> bool:
        """Enable automatic startup."""
        try:
            if self.config.user_level:
                key = winreg.HKEY_CURRENT_USER
                subkey = self.USER_STARTUP_KEY
            else:
                key = winreg.HKEY_LOCAL_MACHINE  
                subkey = self.SYSTEM_STARTUP_KEY
            
            # Create registry entry
            with winreg.OpenKey(key, subkey, 0, winreg.KEY_WRITE) as reg_key:
                command = f'"{self.config.executable_path}"'
                if self.config.arguments:
                    command += f" {self.config.arguments}"
                
                winreg.SetValueEx(
                    reg_key,
                    self.config.app_name,
                    0,
                    winreg.REG_SZ,
                    command
                )
            
            # Enable in Startup Approved (Windows 10+)
            self._set_startup_approved(True)
            
            logger.info(f"Startup enabled: {self.config.app_name}")
            return True
            
        except PermissionError:
            logger.error("Permission denied: Run as administrator for system-level startup")
            return False
        except Exception as e:
            logger.error(f"Error enabling startup: {e}")
            return False
    
    def disable_startup(self) -> bool:
        """Disable automatic startup."""
        try:
            if self.config.user_level:
                key = winreg.HKEY_CURRENT_USER
                subkey = self.USER_STARTUP_KEY
            else:
                key = winreg.HKEY_LOCAL_MACHINE
                subkey = self.SYSTEM_STARTUP_KEY
            
            # Remove registry entry
            with winreg.OpenKey(key, subkey, 0, winreg.KEY_WRITE) as reg_key:
                try:
                    winreg.DeleteValue(reg_key, self.config.app_name)
                except FileNotFoundError:
                    pass  # Already removed
            
            # Disable in Startup Approved
            self._set_startup_approved(False)
            
            logger.info(f"Startup disabled: {self.config.app_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error disabling startup: {e}")
            return False
    
    def _set_startup_approved(self, enabled: bool):
        """Set startup approval status (Windows 10+)."""
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.STARTUP_APPROVED_KEY,
                0,
                winreg.KEY_WRITE
            ) as reg_key:
                # Enabled = 12 bytes of 0x02, Disabled = 12 bytes starting with 0x03
                if enabled:
                    value = b'\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                else:
                    value = b'\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                
                winreg.SetValueEx(
                    reg_key,
                    self.config.app_name,
                    0,
                    winreg.REG_BINARY,
                    value
                )
                
        except Exception as e:
            logger.debug(f"Could not set startup approval: {e}")
    
    def get_startup_info(self) -> Dict:
        """Get current startup configuration information."""
        info = {
            'enabled': self.is_startup_enabled(),
            'app_name': self.config.app_name,
            'display_name': self.config.display_name,
            'user_level': self.config.user_level,
            'executable_path': self.config.executable_path,
            'arguments': self.config.arguments
        }
        
        if info['enabled']:
            info['registry_value'] = self._get_registry_value()
        
        return info
    
    def _get_registry_value(self) -> Optional[str]:
        """Get current registry value."""
        try:
            if self.config.user_level:
                key = winreg.HKEY_CURRENT_USER
                subkey = self.USER_STARTUP_KEY
            else:
                key = winreg.HKEY_LOCAL_MACHINE
                subkey = self.SYSTEM_STARTUP_KEY
            
            with winreg.OpenKey(key, subkey, 0, winreg.KEY_READ) as reg_key:
                value, _ = winreg.QueryValueEx(reg_key, self.config.app_name)
                return value
                
        except Exception:
            return None
    
    def validate_startup_entry(self) -> Tuple[bool, List[str]]:
        """Validate current startup entry."""
        issues = []
        
        if not self.is_startup_enabled():
            return False, ["Startup entry not found"]
        
        registry_value = self._get_registry_value()
        if not registry_value:
            issues.append("Could not read registry value")
            return False, issues
        
        # Check if executable exists
        if '"' in registry_value:
            # Extract executable path from quoted command
            parts = registry_value.split('"')
            if len(parts) >= 2:
                exe_path = parts[1]
            else:
                exe_path = registry_value.split()[0]
        else:
            exe_path = registry_value.split()[0]
        
        if not os.path.exists(exe_path):
            issues.append(f"Executable not found: {exe_path}")
        
        # Check if path matches current configuration
        expected_path = self.config.executable_path.strip('"')
        if exe_path != expected_path:
            issues.append(f"Path mismatch: expected {expected_path}, found {exe_path}")
        
        return len(issues) == 0, issues
    
    def repair_startup_entry(self) -> bool:
        """Repair corrupted startup entry."""
        try:
            logger.info("Repairing startup entry")
            
            # Disable and re-enable to reset
            self.disable_startup()
            return self.enable_startup()
            
        except Exception as e:
            logger.error(f"Error repairing startup entry: {e}")
            return False
    
    def create_startup_shortcut(self, shortcut_path: str = None) -> bool:
        """Create startup shortcut as alternative to registry method."""
        try:
            import pythoncom
            from win32com.shell import shell, shellcon
            
            if not shortcut_path:
                startup_folder = shell.SHGetFolderPath(
                    0, shellcon.CSIDL_STARTUP, None, shellcon.SHGFP_TYPE_CURRENT
                )
                shortcut_path = os.path.join(startup_folder, f"{self.config.app_name}.lnk")
            
            # Create shortcut
            shortcut = pythoncom.CoCreateInstance(
                shell.CLSID_ShellLink,
                None,
                pythoncom.CLSCTX_INPROC_SERVER,
                shell.IID_IShellLink
            )
            
            shortcut.SetPath(self.config.executable_path)
            shortcut.SetArguments(self.config.arguments)
            shortcut.SetDescription(self.config.description)
            shortcut.SetWorkingDirectory(os.path.dirname(self.config.executable_path))
            
            if self.config.start_minimized:
                shortcut.SetShowCmd(7)  # SW_SHOWMINNOACTIVE
            
            # Save shortcut
            persist_file = shortcut.QueryInterface(pythoncom.IID_IPersistFile)
            persist_file.Save(shortcut_path, 0)
            
            logger.info(f"Startup shortcut created: {shortcut_path}")
            return True
            
        except ImportError:
            logger.error("pywin32 not available for shortcut creation")
            return False
        except Exception as e:
            logger.error(f"Error creating startup shortcut: {e}")
            return False
    
    def remove_startup_shortcut(self, shortcut_path: str = None) -> bool:
        """Remove startup shortcut."""
        try:
            if not shortcut_path:
                from win32com.shell import shell, shellcon
                startup_folder = shell.SHGetFolderPath(
                    0, shellcon.CSIDL_STARTUP, None, shellcon.SHGFP_TYPE_CURRENT
                )
                shortcut_path = os.path.join(startup_folder, f"{self.config.app_name}.lnk")
            
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
                logger.info(f"Startup shortcut removed: {shortcut_path}")
                return True
            
            return True  # Already removed
            
        except Exception as e:
            logger.error(f"Error removing startup shortcut: {e}")
            return False
    
    def install_as_service(self) -> bool:
        """Install as Windows service (requires admin privileges)."""
        try:
            # This would require additional service wrapper implementation
            logger.info("Service installation not yet implemented")
            return False
            
        except Exception as e:
            logger.error(f"Error installing service: {e}")
            return False
    
    def uninstall_service(self) -> bool:
        """Uninstall Windows service."""
        try:
            # This would require service management implementation
            logger.info("Service uninstallation not yet implemented")
            return False
            
        except Exception as e:
            logger.error(f"Error uninstalling service: {e}")
            return False
    
    def check_admin_privileges(self) -> bool:
        """Check if running with administrator privileges."""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    
    def request_admin_privileges(self) -> bool:
        """Request administrator privileges (UAC prompt)."""
        try:
            import ctypes
            
            if self.check_admin_privileges():
                return True
            
            # Re-run current script with admin privileges
            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                sys.executable,
                " ".join(sys.argv),
                None,
                1
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error requesting admin privileges: {e}")
            return False
    
    def backup_registry_keys(self, backup_path: str = None) -> bool:
        """Backup relevant registry keys."""
        try:
            if not backup_path:
                backup_path = tempfile.mktemp(suffix=".reg")
            
            # Export registry keys using reg.exe
            if self.config.user_level:
                key_path = f"HKEY_CURRENT_USER\\{self.USER_STARTUP_KEY}"
            else:
                key_path = f"HKEY_LOCAL_MACHINE\\{self.SYSTEM_STARTUP_KEY}"
            
            result = subprocess.run([
                "reg", "export", key_path, backup_path, "/y"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Registry backup created: {backup_path}")
                return True
            else:
                logger.error(f"Registry backup failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error backing up registry: {e}")
            return False
    
    def restore_registry_keys(self, backup_path: str) -> bool:
        """Restore registry keys from backup."""
        try:
            if not os.path.exists(backup_path):
                logger.error(f"Backup file not found: {backup_path}")
                return False
            
            result = subprocess.run([
                "reg", "import", backup_path
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Registry restored from: {backup_path}")
                return True
            else:
                logger.error(f"Registry restore failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error restoring registry: {e}")
            return False
    
    def get_boot_impact_score(self) -> int:
        """Get estimated boot impact score (0-10, lower is better)."""
        # Base score
        score = 2
        
        # Add points for system-level installation
        if not self.config.user_level:
            score += 1
        
        # Add points for complex arguments
        if len(self.config.arguments) > 50:
            score += 1
        
        # Add points for large executable
        try:
            exe_size = os.path.getsize(self.config.executable_path.strip('"'))
            if exe_size > 10 * 1024 * 1024:  # > 10MB
                score += 2
            elif exe_size > 5 * 1024 * 1024:  # > 5MB
                score += 1
        except:
            pass
        
        return min(score, 10)
    
    def optimize_for_boot_performance(self) -> bool:
        """Optimize startup configuration for boot performance."""
        try:
            # Ensure start minimized is enabled
            self.config.start_minimized = True
            
            # Add delay argument if not present
            if "--delay" not in self.config.arguments:
                self.config.arguments += " --delay 10"
            
            # Update registry with optimized settings
            if self.is_startup_enabled():
                return self.enable_startup()  # Re-enable with new settings
            
            return True
            
        except Exception as e:
            logger.error(f"Error optimizing boot performance: {e}")
            return False

# Convenience functions
def enable_startup(app_name: str = "WindowResizer", user_level: bool = True) -> bool:
    """Enable startup for the application."""
    config = StartupConfig(app_name=app_name, user_level=user_level)
    manager = StartupManager(config)
    return manager.enable_startup()

def disable_startup(app_name: str = "WindowResizer", user_level: bool = True) -> bool:
    """Disable startup for the application."""
    config = StartupConfig(app_name=app_name, user_level=user_level)
    manager = StartupManager(config)
    return manager.disable_startup()

def is_startup_enabled(app_name: str = "WindowResizer", user_level: bool = True) -> bool:
    """Check if startup is enabled."""
    config = StartupConfig(app_name=app_name, user_level=user_level)
    manager = StartupManager(config)
    return manager.is_startup_enabled()

# Global startup manager instance
default_startup_manager = StartupManager()

if __name__ == "__main__":
    # Test startup manager
    logging.basicConfig(level=logging.INFO)
    
    manager = StartupManager()
    
    print("Current startup status:", manager.is_startup_enabled())
    print("Startup info:", manager.get_startup_info())
    
    # Test validation
    is_valid, issues = manager.validate_startup_entry()
    print(f"Startup entry valid: {is_valid}")
    if issues:
        print("Issues found:", issues)
    
    print("Boot impact score:", manager.get_boot_impact_score())
    print("Admin privileges:", manager.check_admin_privileges())