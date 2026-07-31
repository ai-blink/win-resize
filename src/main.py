#!/usr/bin/env python3
"""
WindowResizer - Advanced Window Management Tool
==============================================

Main entry point for the standalone application.
"""

import sys
import os
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

def main():
    """Main application entry point."""
    try:
        # Import PyQt5 and create application
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt
        
        # Set application attributes
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # Create application
        app = QApplication(sys.argv)
        app.setApplicationName("WindowResizer")
        app.setApplicationVersion("0.01.2")
        app.setOrganizationName("WindowResizer Team")
        app.setQuitOnLastWindowClosed(False)
        
        # Import and create main window
        from gui.main_window import WindowResizerMainWindow
        window = WindowResizerMainWindow()
        window.show()
        
        # Run application
        return app.exec_()
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Please ensure all dependencies are installed.")
        return 1
    except Exception as e:
        print(f"Application error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
