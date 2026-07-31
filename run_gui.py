"""
WindowResizer GUI Launcher
==========================

Launches the WindowResizer GUI application with proper initialization
and error handling.
"""

import sys
import os
import logging
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
    app.setApplicationVersion("0.01.1")
    app.setOrganizationName("WindowResizer")
    app.setQuitOnLastWindowClosed(False)
    
    try:
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

if __name__ == "__main__":
    sys.exit(main())
