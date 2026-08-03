"""
WindowResizer GUI Launcher
==========================

Launches the WindowResizer GUI application with proper initialization
and error handling.
"""

import sys
import os
import logging
import ctypes
from ctypes import wintypes
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtCore import Qt
    from gui.main_window import WindowResizerMainWindow
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure PyQt5 is installed: pip install PyQt5")
    sys.exit(1)


MUTEX_NAME = r"Local\WindowResizer.SingleInstance"
ERROR_ALREADY_EXISTS = 183


class SingleInstanceGuard:
    """Keep the main application limited to one Windows session instance."""

    def __init__(self, mutex_name=MUTEX_NAME, kernel32=None):
        self.mutex_name = mutex_name
        self._kernel32 = kernel32 or self._load_kernel32()
        self._mutex_handle = None

    @staticmethod
    def _load_kernel32():
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        )
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        return kernel32

    def acquire(self):
        """Return True when this process owns the application mutex."""
        if self._mutex_handle is not None:
            return True

        ctypes.set_last_error(0)
        handle = self._kernel32.CreateMutexW(None, False, self.mutex_name)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateMutexW failed")

        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            self._kernel32.CloseHandle(handle)
            return False

        self._mutex_handle = handle
        return True

    def release(self):
        """Release the mutex so a future launch can become the main instance."""
        if self._mutex_handle is not None:
            self._kernel32.CloseHandle(self._mutex_handle)
            self._mutex_handle = None


def setup_logging():
    """Setup logging for the GUI application."""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "windowresizer_gui.log"),
            logging.StreamHandler()
        ]
    )


def configure_high_dpi():
    """Configure Qt high-DPI behavior before creating QApplication."""
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

def main():
    """Main application entry point."""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting WindowResizer GUI Application")
    
    configure_high_dpi()

    # Create QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("WindowResizer")
    app.setApplicationVersion("0.01.3")
    app.setOrganizationName("WindowResizer")
    app.setQuitOnLastWindowClosed(False)
    
    instance_guard = SingleInstanceGuard()

    try:
        if not instance_guard.acquire():
            logger.info("WindowResizer is already running")
            QMessageBox.information(
                None,
                "WindowResizer",
                "WindowResizer is already running.",
            )
            return 0

        # Create and show main window
        window = WindowResizerMainWindow()
        window.show()
        
        logger.info("GUI application started successfully")
        
        # Run application
        return app.exec_()
        
    except Exception as e:
        logger.error(f"Failed to start GUI application: {e}")
        
        # Show error message
        error_msg = QMessageBox()
        error_msg.setIcon(QMessageBox.Critical)
        error_msg.setWindowTitle("Startup Error")
        error_msg.setText("Failed to start WindowResizer")
        error_msg.setDetailedText(str(e))
        error_msg.exec_()
        
        return 1
    finally:
        instance_guard.release()

if __name__ == "__main__":
    sys.exit(main())
