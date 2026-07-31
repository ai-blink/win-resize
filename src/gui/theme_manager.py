"""
Theme Management System
=======================

Comprehensive theme management for dark/light mode support with
system integration and user customization options.

Key Features:
- Dark and light theme variants
- System theme auto-detection (Windows 10/11)
- Custom color scheme support
- Icon and UI element updates per theme
- Accessibility improvements
- Theme persistence and restoration
- Smooth theme transitions
- Per-component theming
"""

import sys
import os
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import QObject, pyqtSignal, QSettings, QTimer
from PyQt5.QtGui import QPalette, QColor, QFont, QIcon, QPixmap, QPainter
from PyQt5.QtCore import Qt

logger = logging.getLogger(__name__)

class ThemeType(Enum):
    """Available theme types."""
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"  # Follow system theme
    CUSTOM = "custom"

class ThemeElement(Enum):
    """UI elements that can be themed."""
    BACKGROUND = "background"
    FOREGROUND = "foreground"
    BUTTON = "button"
    BUTTON_HOVER = "button_hover"
    BUTTON_PRESSED = "button_pressed"
    TEXT = "text"
    ACCENT = "accent"
    BORDER = "border"
    SELECTION = "selection"
    DISABLED = "disabled"
    ERROR = "error"
    SUCCESS = "success"
    WARNING = "warning"
    INFO = "info"

@dataclass
class ColorScheme:
    """Color scheme definition for a theme."""
    name: str
    colors: Dict[ThemeElement, str] = field(default_factory=dict)
    description: str = ""
    author: str = ""
    version: str = "1.0"
    
    def __post_init__(self):
        """Initialize default colors if not provided."""
        if not self.colors:
            self.colors = self._get_default_colors()
    
    def _get_default_colors(self) -> Dict[ThemeElement, str]:
        """Get default color scheme."""
        return {
            ThemeElement.BACKGROUND: "#ffffff",
            ThemeElement.FOREGROUND: "#000000",
            ThemeElement.BUTTON: "#f0f0f0",
            ThemeElement.BUTTON_HOVER: "#e0e0e0",
            ThemeElement.BUTTON_PRESSED: "#d0d0d0",
            ThemeElement.TEXT: "#000000",
            ThemeElement.ACCENT: "#0078d4",
            ThemeElement.BORDER: "#cccccc",
            ThemeElement.SELECTION: "#0078d4",
            ThemeElement.DISABLED: "#999999",
            ThemeElement.ERROR: "#d32f2f",
            ThemeElement.SUCCESS: "#388e3c",
            ThemeElement.WARNING: "#f57c00",
            ThemeElement.INFO: "#1976d2"
        }
    
    def get_color(self, element: ThemeElement) -> QColor:
        """Get QColor for theme element."""
        color_str = self.colors.get(element, "#000000")
        return QColor(color_str)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'colors': {element.value: color for element, color in self.colors.items()},
            'description': self.description,
            'author': self.author,
            'version': self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ColorScheme':
        """Create from dictionary."""
        colors = {}
        for element_str, color in data.get('colors', {}).items():
            try:
                element = ThemeElement(element_str)
                colors[element] = color
            except ValueError:
                continue
        
        return cls(
            name=data.get('name', 'Unnamed'),
            colors=colors,
            description=data.get('description', ''),
            author=data.get('author', ''),
            version=data.get('version', '1.0')
        )

class ThemeManager(QObject):
    """Manages application themes and color schemes."""
    
    # Signals
    theme_changed = pyqtSignal(str)  # theme_name
    color_scheme_changed = pyqtSignal(str)  # scheme_name
    system_theme_detected = pyqtSignal(str)  # detected_theme
    
    def __init__(self):
        """Initialize theme manager."""
        super().__init__()
        
        self.current_theme = ThemeType.LIGHT
        self.current_scheme: Optional[ColorScheme] = None
        self.color_schemes: Dict[str, ColorScheme] = {}
        self.follow_system = False  # 시스템 테마 추적 비활성화
        
        # Settings
        self.settings = QSettings("WindowResizer", "ThemeManager")
        
        # System theme monitoring
        self.system_theme_timer = QTimer()
        self.system_theme_timer.timeout.connect(self._check_system_theme)
        self.last_system_theme = None
        
        # Initialize built-in themes
        self._create_builtin_themes()
        
        # Load user themes
        self._load_user_themes()
        
        # Apply saved theme or detect system theme
        self._initialize_theme()
        self._apply_theme_to_application()
        
        logger.info("ThemeManager initialized")
    
    def _create_builtin_themes(self):
        """Create built-in color schemes."""
        # Light theme
        light_scheme = ColorScheme(
            name="Light",
            colors={
                ThemeElement.BACKGROUND: "#ffffff",
                ThemeElement.FOREGROUND: "#f8f9fa",
                ThemeElement.BUTTON: "#f1f3f4",
                ThemeElement.BUTTON_HOVER: "#e8eaed",
                ThemeElement.BUTTON_PRESSED: "#dadce0",
                ThemeElement.TEXT: "#202124",
                ThemeElement.ACCENT: "#1a73e8",
                ThemeElement.BORDER: "#dadce0",
                ThemeElement.SELECTION: "#1a73e8",
                ThemeElement.DISABLED: "#80868b",
                ThemeElement.ERROR: "#d93025",
                ThemeElement.SUCCESS: "#137333",
                ThemeElement.WARNING: "#ea8600",
                ThemeElement.INFO: "#1967d2"
            },
            description="Clean light theme with modern colors",
            author="WindowResizer Team",
            version="1.0"
        )
        
        # Dark theme
        dark_scheme = ColorScheme(
            name="Dark",
            colors={
                ThemeElement.BACKGROUND: "#202124",
                ThemeElement.FOREGROUND: "#2d2e30",
                ThemeElement.BUTTON: "#3c4043",
                ThemeElement.BUTTON_HOVER: "#48494c",
                ThemeElement.BUTTON_PRESSED: "#5f6368",
                ThemeElement.TEXT: "#e8eaed",
                ThemeElement.ACCENT: "#8ab4f8",
                ThemeElement.BORDER: "#5f6368",
                ThemeElement.SELECTION: "#8ab4f8",
                ThemeElement.DISABLED: "#80868b",
                ThemeElement.ERROR: "#f28b82",
                ThemeElement.SUCCESS: "#81c995",
                ThemeElement.WARNING: "#fdd663",
                ThemeElement.INFO: "#8ab4f8"
            },
            description="Modern dark theme for reduced eye strain",
            author="WindowResizer Team",
            version="1.0"
        )
        
        # High contrast theme
        high_contrast_scheme = ColorScheme(
            name="High Contrast",
            colors={
                ThemeElement.BACKGROUND: "#000000",
                ThemeElement.FOREGROUND: "#1a1a1a",
                ThemeElement.BUTTON: "#333333",
                ThemeElement.BUTTON_HOVER: "#444444",
                ThemeElement.BUTTON_PRESSED: "#555555",
                ThemeElement.TEXT: "#ffffff",
                ThemeElement.ACCENT: "#ffff00",
                ThemeElement.BORDER: "#ffffff",
                ThemeElement.SELECTION: "#ffff00",
                ThemeElement.DISABLED: "#808080",
                ThemeElement.ERROR: "#ff0000",
                ThemeElement.SUCCESS: "#00ff00",
                ThemeElement.WARNING: "#ffaa00",
                ThemeElement.INFO: "#00ffff"
            },
            description="High contrast theme for accessibility",
            author="WindowResizer Team",
            version="1.0"
        )
        
        self.color_schemes[light_scheme.name] = light_scheme
        self.color_schemes[dark_scheme.name] = dark_scheme
        self.color_schemes[high_contrast_scheme.name] = high_contrast_scheme
    
    def _load_user_themes(self):
        """Load user-defined themes from file."""
        themes_dir = Path.home() / "AppData" / "Local" / "WindowResizer" / "themes"
        
        if not themes_dir.exists():
            return
        
        for theme_file in themes_dir.glob("*.json"):
            try:
                with open(theme_file, 'r', encoding='utf-8') as f:
                    theme_data = json.load(f)
                
                scheme = ColorScheme.from_dict(theme_data)
                self.color_schemes[scheme.name] = scheme
                
                logger.info(f"Loaded user theme: {scheme.name}")
                
            except Exception as e:
                logger.error(f"Error loading theme {theme_file}: {e}")
    
    def _initialize_theme(self):
        """Initialize theme based on settings or system detection."""
        # Load saved theme preference
        saved_theme = self.settings.value("theme", "system")
        saved_scheme = self.settings.value("color_scheme", "Light")
        follow_system = self.settings.value("follow_system", False, type=bool)
        should_follow_system = saved_theme == ThemeType.SYSTEM.value or follow_system

        self.follow_system = should_follow_system

        if should_follow_system:
            detected_theme = self._detect_system_theme()
            self.last_system_theme = detected_theme
            if detected_theme == ThemeType.DARK.value:
                self.current_theme = ThemeType.DARK
                scheme_name = "Dark"
            else:
                self.current_theme = ThemeType.LIGHT
                scheme_name = "Light"
            self.system_theme_timer.start(5000)
        else:
            try:
                self.current_theme = ThemeType(saved_theme)
                scheme_name = saved_scheme
            except ValueError:
                self.current_theme = ThemeType.LIGHT
                scheme_name = "Light"
        
        # Set color scheme
        if scheme_name in self.color_schemes:
            self.current_scheme = self.color_schemes[scheme_name]
        else:
            self.current_scheme = self.color_schemes["Light"]
        
        logger.info(f"Initialized theme: {self.current_theme.value} with scheme: {self.current_scheme.name}")
    
    def _detect_system_theme(self) -> Optional[str]:
        """Detect system theme preference (Windows 10/11)."""
        if not WINREG_AVAILABLE:
            return None
        
        try:
            # Windows 10/11 theme detection
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                # AppsUseLightTheme: 0 = dark, 1 = light
                apps_light_theme = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
                
                return "light" if apps_light_theme else "dark"
                
        except Exception as e:
            logger.debug(f"Could not detect system theme: {e}")
            return None
    
    def _check_system_theme(self):
        """Check for system theme changes."""
        if not self.follow_system:
            return
        
        current_system_theme = self._detect_system_theme()
        
        if current_system_theme and current_system_theme != self.last_system_theme:
            self.last_system_theme = current_system_theme
            
            # Update theme
            if current_system_theme == "dark":
                self.set_theme(ThemeType.DARK, "Dark")
            else:
                self.set_theme(ThemeType.LIGHT, "Light")
            
            self.system_theme_detected.emit(current_system_theme)
            logger.info(f"System theme changed to: {current_system_theme}")
    
    def set_theme(self, theme_type: ThemeType, scheme_name: str = None) -> bool:
        """Set the current theme and color scheme."""
        try:
            self.current_theme = theme_type
            
            # Determine scheme
            if scheme_name and scheme_name in self.color_schemes:
                self.current_scheme = self.color_schemes[scheme_name]
            elif theme_type == ThemeType.DARK:
                self.current_scheme = self.color_schemes.get("Dark", self.color_schemes["Light"])
            elif theme_type == ThemeType.LIGHT:
                self.current_scheme = self.color_schemes.get("Light")
            else:
                # Keep current scheme
                pass
            
            # Apply theme to application
            self._apply_theme_to_application()
            
            # Save settings
            self.settings.setValue("theme", theme_type.value)
            if self.current_scheme:
                self.settings.setValue("color_scheme", self.current_scheme.name)
            
            # Emit signals
            self.theme_changed.emit(theme_type.value)
            if self.current_scheme:
                self.color_scheme_changed.emit(self.current_scheme.name)
            
            logger.info(f"Theme changed to: {theme_type.value} ({self.current_scheme.name if self.current_scheme else 'No scheme'})")
            return True
            
        except Exception as e:
            logger.error(f"Error setting theme: {e}")
            return False
    
    def _apply_theme_to_application(self):
        """Apply current theme to the Qt application."""
        app = QApplication.instance()
        if not app or not self.current_scheme:
            return
        
        try:
            # Create QPalette from color scheme
            palette = QPalette()
            
            # Window colors
            palette.setColor(QPalette.Window, self.current_scheme.get_color(ThemeElement.BACKGROUND))
            palette.setColor(QPalette.WindowText, self.current_scheme.get_color(ThemeElement.TEXT))
            
            # Base colors (for input fields)
            palette.setColor(QPalette.Base, self.current_scheme.get_color(ThemeElement.FOREGROUND))
            palette.setColor(QPalette.AlternateBase, self.current_scheme.get_color(ThemeElement.BUTTON))
            
            # Text colors
            palette.setColor(QPalette.Text, self.current_scheme.get_color(ThemeElement.TEXT))
            palette.setColor(QPalette.BrightText, self.current_scheme.get_color(ThemeElement.TEXT))
            
            # Button colors
            palette.setColor(QPalette.Button, self.current_scheme.get_color(ThemeElement.BUTTON))
            palette.setColor(QPalette.ButtonText, self.current_scheme.get_color(ThemeElement.TEXT))
            
            # Selection colors
            selection_color = self.current_scheme.get_color(ThemeElement.SELECTION)
            palette.setColor(QPalette.Highlight, selection_color)
            palette.setColor(QPalette.HighlightedText, self._get_selection_text_color(selection_color))
            
            # Disabled colors
            disabled_color = self.current_scheme.get_color(ThemeElement.DISABLED)
            palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_color)
            palette.setColor(QPalette.Disabled, QPalette.Text, disabled_color)
            palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_color)
            
            # Apply palette
            app.setPalette(palette)
            
            # Update stylesheets for enhanced theming
            self._apply_custom_stylesheets()
            
        except Exception as e:
            logger.error(f"Error applying theme to application: {e}")

    @staticmethod
    def _get_selection_text_color(selection_color: QColor) -> QColor:
        """Return a readable text color for the active selection color."""
        if selection_color.lightness() > 127:
            return QColor("#000000")
        return QColor("#ffffff")
    
    def _apply_custom_stylesheets(self):
        """Apply custom stylesheets for enhanced theming."""
        if not self.current_scheme:
            return
        
        try:
            # Get colors
            bg = self.current_scheme.colors[ThemeElement.BACKGROUND]
            fg = self.current_scheme.colors[ThemeElement.FOREGROUND]
            button = self.current_scheme.colors[ThemeElement.BUTTON]
            button_hover = self.current_scheme.colors[ThemeElement.BUTTON_HOVER]
            button_pressed = self.current_scheme.colors[ThemeElement.BUTTON_PRESSED]
            text = self.current_scheme.colors[ThemeElement.TEXT]
            accent = self.current_scheme.colors[ThemeElement.ACCENT]
            border = self.current_scheme.colors[ThemeElement.BORDER]
            
            # Custom stylesheet
            stylesheet = f"""
            QMainWindow {{
                background-color: {bg};
                color: {text};
            }}
            
            QGroupBox {{
                background-color: {fg};
                border: 1px solid {border};
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                padding-top: 5px;
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: {text};
            }}
            
            QPushButton {{
                background-color: {button};
                border: 1px solid {border};
                border-radius: 3px;
                padding: 5px 10px;
                color: {text};
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: {button_hover};
            }}
            
            QPushButton:pressed {{
                background-color: {button_pressed};
            }}
            
            QPushButton:disabled {{
                background-color: {border};
                color: {self.current_scheme.colors[ThemeElement.DISABLED]};
            }}
            
            QLineEdit, QSpinBox {{
                background-color: {fg};
                border: 1px solid {border};
                border-radius: 3px;
                padding: 3px;
                color: {text};
            }}
            
            QLineEdit:focus, QSpinBox:focus {{
                border: 2px solid {accent};
            }}
            
            QListWidget {{
                background-color: {fg};
                border: 1px solid {border};
                border-radius: 3px;
                color: {text};
                selection-background-color: {accent};
            }}
            
            QListWidget::item {{
                padding: 3px;
                border-bottom: 1px solid {border};
            }}
            
            QListWidget::item:selected {{
                background-color: {accent};
                color: {bg};
            }}
            
            QComboBox {{
                background-color: {button};
                border: 1px solid {border};
                border-radius: 3px;
                padding: 3px;
                color: {text};
            }}
            
            QComboBox:hover {{
                background-color: {button_hover};
            }}
            
            QComboBox::drop-down {{
                border: none;
            }}
            
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {text};
            }}
            
            QCheckBox {{
                color: {text};
            }}
            
            QCheckBox::indicator {{
                width: 13px;
                height: 13px;
                background-color: {fg};
                border: 1px solid {border};
                border-radius: 2px;
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {accent};
            }}
            
            QStatusBar {{
                background-color: {fg};
                border-top: 1px solid {border};
                color: {text};
            }}
            
            QMenuBar {{
                background-color: {fg};
                color: {text};
            }}
            
            QMenuBar::item:selected {{
                background-color: {accent};
                color: {bg};
            }}
            
            QMenu {{
                background-color: {fg};
                border: 1px solid {border};
                color: {text};
            }}
            
            QMenu::item:selected {{
                background-color: {accent};
                color: {bg};
            }}
            
            /* QMessageBox styling for better dark mode visibility */
            QMessageBox {{
                background-color: {fg};
                color: {text};
            }}
            
            QMessageBox QLabel {{
                background-color: {fg};
                color: {text};
                font-size: 11pt;
                padding: 10px;
            }}
            
            QMessageBox QPushButton {{
                background-color: {button};
                border: 1px solid {border};
                border-radius: 3px;
                padding: 8px 16px;
                color: {text};
                font-weight: bold;
                min-width: 70px;
                min-height: 20px;
            }}
            
            QMessageBox QPushButton:hover {{
                background-color: {button_hover};
            }}
            
            QMessageBox QPushButton:pressed {{
                background-color: {button_pressed};
            }}
            
            QMessageBox QPushButton:default {{
                background-color: {accent};
                color: {bg};
            }}
            
            QMessageBox QPushButton:default:hover {{
                background-color: {accent};
                color: {bg};
                border: 2px solid {text};
            }}
            
            /* Dialog styling */
            QDialog {{
                background-color: {fg};
                color: {text};
            }}
            
            QDialog QLabel {{
                color: {text};
                background-color: transparent;
            }}
            
            QTabWidget::pane {{
                background-color: {fg};
                border: 1px solid {border};
                border-radius: 3px;
            }}
            
            QTabWidget::tab-bar {{
                left: 5px;
            }}
            
            QTabBar::tab {{
                background-color: {button};
                border: 1px solid {border};
                border-bottom-color: {border};
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 8ex;
                padding: 6px 12px;
                color: {text};
            }}
            
            QTabBar::tab:selected, QTabBar::tab:hover {{
                background-color: {accent};
                color: {bg};
            }}
            
            QTabBar::tab:selected {{
                border-color: {accent};
                border-bottom-color: {fg};
            }}
            
            QTextEdit {{
                background-color: {fg};
                border: 1px solid {border};
                border-radius: 3px;
                color: {text};
                padding: 3px;
            }}
            
            QFormLayout QLabel {{
                color: {text};
            }}
            """
            
            app = QApplication.instance()
            if app:
                app.setStyleSheet(stylesheet)
                
        except Exception as e:
            logger.error(f"Error applying custom stylesheets: {e}")
    
    def get_color(self, element: ThemeElement) -> QColor:
        """Get color for a theme element."""
        if self.current_scheme:
            return self.current_scheme.get_color(element)
        return QColor("#000000")
    
    def get_color_string(self, element: ThemeElement) -> str:
        """Get color string for a theme element."""
        if self.current_scheme and element in self.current_scheme.colors:
            return self.current_scheme.colors[element]
        return "#000000"
    
    def get_message_box_style(self) -> str:
        """Get styled QMessageBox CSS for current theme."""
        if not self.current_scheme:
            return ""
        
        # Use current color scheme values
        bg = self.get_color_string(ThemeElement.BACKGROUND)
        fg = self.get_color_string(ThemeElement.FOREGROUND) 
        text = self.get_color_string(ThemeElement.TEXT)
        button = self.get_color_string(ThemeElement.BUTTON)
        button_hover = self.get_color_string(ThemeElement.BUTTON_HOVER)
        button_pressed = self.get_color_string(ThemeElement.BUTTON_PRESSED)
        accent = self.get_color_string(ThemeElement.ACCENT)
        border = self.get_color_string(ThemeElement.BORDER)
        
        return f"""
        QMessageBox {{
            background-color: {fg};
            color: {text};
            border: 2px solid {border};
            border-radius: 8px;
            font-size: 11pt;
            padding: 15px;
        }}
        
        QMessageBox QLabel {{
            background-color: transparent;
            color: {text};
            font-size: 12pt;
            font-weight: normal;
            padding: 10px;
            border: none;
        }}
        
        QMessageBox QPushButton {{
            background-color: {button};
            border: 2px solid {border};
            border-radius: 6px;
            padding: 10px 20px;
            color: {text};
            font-weight: bold;
            font-size: 10pt;
            min-width: 80px;
            min-height: 25px;
        }}
        
        QMessageBox QPushButton:hover {{
            background-color: {button_hover};
            border: 2px solid {accent};
        }}
        
        QMessageBox QPushButton:pressed {{
            background-color: {button_pressed};
        }}
        
        QMessageBox QPushButton:default {{
            background-color: {accent};
            color: {bg};
            border: 2px solid {accent};
        }}
        
        QMessageBox QPushButton:default:hover {{
            background-color: {accent};
            color: {bg};
            border: 2px solid {text};
        }}
        """
    
    def set_follow_system(self, follow: bool):
        """Set whether to follow system theme."""
        self.follow_system = follow
        self.settings.setValue("follow_system", follow)
        
        if follow:
            # Start monitoring and apply current system theme
            self.system_theme_timer.start(5000)
            self._check_system_theme()
        else:
            # Stop monitoring
            self.system_theme_timer.stop()
        
        logger.info(f"Follow system theme: {'enabled' if follow else 'disabled'}")
    
    def add_color_scheme(self, scheme: ColorScheme) -> bool:
        """Add a custom color scheme."""
        try:
            self.color_schemes[scheme.name] = scheme
            
            # Save to file
            self._save_user_theme(scheme)
            
            logger.info(f"Added color scheme: {scheme.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding color scheme: {e}")
            return False
    
    def remove_color_scheme(self, scheme_name: str) -> bool:
        """Remove a color scheme."""
        if scheme_name in ["Light", "Dark", "High Contrast"]:
            logger.warning("Cannot remove built-in themes")
            return False
        
        if scheme_name not in self.color_schemes:
            return False
        
        try:
            del self.color_schemes[scheme_name]
            
            # Remove file
            themes_dir = Path.home() / "AppData" / "Local" / "WindowResizer" / "themes"
            theme_file = themes_dir / f"{scheme_name}.json"
            if theme_file.exists():
                theme_file.unlink()
            
            logger.info(f"Removed color scheme: {scheme_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing color scheme: {e}")
            return False
    
    def _save_user_theme(self, scheme: ColorScheme):
        """Save user theme to file."""
        themes_dir = Path.home() / "AppData" / "Local" / "WindowResizer" / "themes"
        themes_dir.mkdir(parents=True, exist_ok=True)
        
        theme_file = themes_dir / f"{scheme.name}.json"
        
        with open(theme_file, 'w', encoding='utf-8') as f:
            json.dump(scheme.to_dict(), f, indent=2, ensure_ascii=False)
    
    def get_available_schemes(self) -> List[str]:
        """Get list of available color scheme names."""
        return list(self.color_schemes.keys())
    
    def get_current_theme_info(self) -> Dict[str, Any]:
        """Get current theme information."""
        return {
            'theme_type': self.current_theme.value,
            'color_scheme': self.current_scheme.name if self.current_scheme else None,
            'follow_system': self.follow_system,
            'system_theme': self._detect_system_theme()
        }
    
    def create_themed_icon(self, icon_name: str, size: int = 16) -> QIcon:
        """Create a themed icon with current colors."""
        try:
            # Create a simple colored icon
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Use accent color for icons
            color = self.get_color(ThemeElement.ACCENT)
            painter.setBrush(color)
            painter.setPen(color)
            
            # Draw based on icon name
            if icon_name == "settings":
                painter.drawEllipse(2, 2, size-4, size-4)
                painter.drawEllipse(size//2-2, size//2-2, 4, 4)
            elif icon_name == "theme":
                painter.drawEllipse(2, 2, size//2-2, size//2-2)
                painter.fillRect(size//2, 2, size//2-2, size//2-2, color)
            else:
                # Default icon
                painter.drawRect(2, 2, size-4, size-4)
            
            painter.end()
            
            return QIcon(pixmap)
            
        except Exception as e:
            logger.error(f"Error creating themed icon: {e}")
            return QIcon()

# Global theme manager instance
default_theme_manager = None

def get_theme_manager() -> ThemeManager:
    """Get or create the global theme manager."""
    global default_theme_manager
    
    if default_theme_manager is None:
        default_theme_manager = ThemeManager()
    
    return default_theme_manager

def apply_theme_to_widget(widget: QWidget, theme_manager: ThemeManager = None):
    """Apply current theme to a specific widget."""
    if not theme_manager:
        theme_manager = get_theme_manager()
    
    if not theme_manager.current_scheme:
        return
    
    try:
        # Apply basic colors
        palette = widget.palette()
        
        palette.setColor(QPalette.Window, theme_manager.get_color(ThemeElement.BACKGROUND))
        palette.setColor(QPalette.WindowText, theme_manager.get_color(ThemeElement.TEXT))
        palette.setColor(QPalette.Base, theme_manager.get_color(ThemeElement.FOREGROUND))
        palette.setColor(QPalette.Text, theme_manager.get_color(ThemeElement.TEXT))
        
        widget.setPalette(palette)
        
    except Exception as e:
        logger.error(f"Error applying theme to widget: {e}")

if __name__ == "__main__":
    # Test theme manager
    import logging
    from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
    
    logging.basicConfig(level=logging.INFO)
    
    app = QApplication(sys.argv)
    
    # Create theme manager
    theme_manager = ThemeManager()
    
    # Create test window
    window = QMainWindow()
    window.setWindowTitle("Theme Manager Test")
    window.resize(400, 300)
    
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)
    
    # Theme toggle buttons
    light_button = QPushButton("Light Theme")
    light_button.clicked.connect(lambda: theme_manager.set_theme(ThemeType.LIGHT, "Light"))
    layout.addWidget(light_button)
    
    dark_button = QPushButton("Dark Theme")
    dark_button.clicked.connect(lambda: theme_manager.set_theme(ThemeType.DARK, "Dark"))
    layout.addWidget(dark_button)
    
    high_contrast_button = QPushButton("High Contrast Theme")
    high_contrast_button.clicked.connect(lambda: theme_manager.set_theme(ThemeType.CUSTOM, "High Contrast"))
    layout.addWidget(high_contrast_button)
    
    system_button = QPushButton("Follow System Theme")
    system_button.clicked.connect(lambda: theme_manager.set_follow_system(True))
    layout.addWidget(system_button)
    
    window.setCentralWidget(central_widget)
    
    # Connect theme change signal
    def on_theme_changed(theme_name):
        print(f"Theme changed to: {theme_name}")
    
    theme_manager.theme_changed.connect(on_theme_changed)
    
    # Show window
    window.show()
    
    print("Theme manager test running. Try the theme buttons!")
    print(f"Available schemes: {theme_manager.get_available_schemes()}")
    print(f"Current theme info: {theme_manager.get_current_theme_info()}")
    
    sys.exit(app.exec_())
