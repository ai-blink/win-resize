"""
Preset Resolution Controls and Window Search
===========================================

Advanced preset resolution system with quick-access buttons and
intelligent window search functionality for enhanced user experience.

Key Features:
- Common resolution presets (1080p, 1440p, 4K, etc.)
- Custom preset creation and management
- Real-time window search with filtering
- Multi-monitor aware positioning
- Quick size templates for common use cases
- Recent window history
- Search by window title, process name, or class
"""

import sys
import os
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re

try:
    import win32api
    import win32con
    import win32gui
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLineEdit,
    QLabel, QComboBox, QListWidget, QListWidgetItem, QGroupBox, QSpinBox,
    QCheckBox, QTabWidget, QScrollArea, QFrame, QCompleter, QMenu, QAction,
    QSplitter, QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PyQt5.QtCore import (
    QObject, pyqtSignal, QTimer, QThread, QMutex, QSettings, Qt, QSize,
    QStringListModel, QSortFilterProxyModel
)
from PyQt5.QtGui import QFont, QIcon, QPalette, QPixmap, QPainter

logger = logging.getLogger(__name__)

class PresetType(Enum):
    """Types of resolution presets."""
    STANDARD = "standard"
    GAMING = "gaming"
    WORK = "work"
    MEDIA = "media"
    CUSTOM = "custom"

class PositionPreset(Enum):
    """Window positioning presets."""
    CENTER = "center"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    LEFT_HALF = "left_half"
    RIGHT_HALF = "right_half"
    TOP_HALF = "top_half"
    BOTTOM_HALF = "bottom_half"

@dataclass
class ResolutionPreset:
    """Resolution preset definition."""
    name: str
    width: int
    height: int
    preset_type: PresetType = PresetType.STANDARD
    position: PositionPreset = PositionPreset.CENTER
    description: str = ""
    hotkey: str = ""
    created_by_user: bool = False
    usage_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'width': self.width,
            'height': self.height,
            'preset_type': self.preset_type.value,
            'position': self.position.value,
            'description': self.description,
            'hotkey': self.hotkey,
            'created_by_user': self.created_by_user,
            'usage_count': self.usage_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResolutionPreset':
        """Create from dictionary."""
        return cls(
            name=data.get('name', ''),
            width=data.get('width', 1920),
            height=data.get('height', 1080),
            preset_type=PresetType(data.get('preset_type', 'standard')),
            position=PositionPreset(data.get('position', 'center')),
            description=data.get('description', ''),
            hotkey=data.get('hotkey', ''),
            created_by_user=data.get('created_by_user', False),
            usage_count=data.get('usage_count', 0)
        )

@dataclass
class WindowSearchResult:
    """Window search result."""
    hwnd: int
    title: str
    class_name: str
    process_name: str
    process_id: int
    is_visible: bool
    rect: Tuple[int, int, int, int]
    relevance_score: float = 0.0

class WindowSearchThread(QThread):
    """Background thread for window search operations."""
    
    results_ready = pyqtSignal(list)  # List[WindowSearchResult]
    
    def __init__(self):
        super().__init__()
        self.search_query = ""
        self.search_visible_only = True
        self.mutex = QMutex()
        self.running = True
    
    def set_search_params(self, query: str, visible_only: bool = True):
        """Set search parameters."""
        self.mutex.lock()
        self.search_query = query.lower()
        self.search_visible_only = visible_only
        self.mutex.unlock()
    
    def run(self):
        """Run search operation."""
        if not WIN32_AVAILABLE:
            return
        
        results = []
        
        def enum_windows_proc(hwnd, param):
            try:
                if not win32gui.IsWindow(hwnd):
                    return True
                
                # Get window info
                title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                is_visible = win32gui.IsWindowVisible(hwnd)
                
                # Skip if filtering for visible only
                if self.search_visible_only and not is_visible:
                    return True
                
                # Get process info
                try:
                    _, process_id = win32process.GetWindowThreadProcessId(hwnd)
                    process_handle = win32api.OpenProcess(
                        win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                        False, process_id
                    )
                    process_name = win32process.GetModuleFileNameEx(process_handle, 0)
                    process_name = os.path.basename(process_name)
                    win32api.CloseHandle(process_handle)
                except:
                    process_name = "unknown"
                    process_id = 0
                
                # Get window rect
                try:
                    rect = win32gui.GetWindowRect(hwnd)
                except:
                    rect = (0, 0, 0, 0)
                
                # Calculate relevance score
                relevance_score = self._calculate_relevance(
                    self.search_query, title, class_name, process_name
                )
                
                # Only include if relevant or no search query
                if not self.search_query or relevance_score > 0:
                    result = WindowSearchResult(
                        hwnd=hwnd,
                        title=title,
                        class_name=class_name,
                        process_name=process_name,
                        process_id=process_id,
                        is_visible=is_visible,
                        rect=rect,
                        relevance_score=relevance_score
                    )
                    results.append(result)
                
                return True
                
            except Exception as e:
                logger.debug(f"Error processing window {hwnd}: {e}")
                return True
        
        try:
            win32gui.EnumWindows(enum_windows_proc, None)
            
            # Sort by relevance score (descending)
            results.sort(key=lambda x: x.relevance_score, reverse=True)
            
            self.results_ready.emit(results)
            
        except Exception as e:
            logger.error(f"Error in window search: {e}")
    
    def _calculate_relevance(self, query: str, title: str, class_name: str, process_name: str) -> float:
        """Calculate search relevance score."""
        if not query:
            return 1.0
        
        score = 0.0
        
        # Exact matches get highest score
        if query in title.lower():
            score += 10.0
        if query in process_name.lower():
            score += 8.0
        if query in class_name.lower():
            score += 6.0
        
        # Partial matches
        words = query.split()
        for word in words:
            if word in title.lower():
                score += 5.0
            if word in process_name.lower():
                score += 3.0
            if word in class_name.lower():
                score += 2.0
        
        # Fuzzy matching
        title_words = title.lower().split()
        for title_word in title_words:
            if any(word in title_word or title_word in word for word in words):
                score += 1.0
        
        return score
    
    def stop(self):
        """Stop the search thread."""
        self.running = False
        self.quit()
        self.wait()

class PresetManager(QObject):
    """Manages resolution presets."""
    
    presets_changed = pyqtSignal()
    preset_applied = pyqtSignal(str, int, int)  # name, width, height
    
    def __init__(self):
        super().__init__()
        self.presets: Dict[str, ResolutionPreset] = {}
        self.settings = QSettings("WindowResizer", "PresetManager")
        self._create_builtin_presets()
        self._load_user_presets()
    
    def _create_builtin_presets(self):
        """Create built-in resolution presets."""
        builtin_presets = [
            # Standard resolutions
            ResolutionPreset("HD (720p)", 1280, 720, PresetType.STANDARD, 
                           description="Standard HD resolution"),
            ResolutionPreset("Full HD (1080p)", 1920, 1080, PresetType.STANDARD,
                           description="Full HD resolution"),
            ResolutionPreset("QHD (1440p)", 2560, 1440, PresetType.STANDARD,
                           description="Quad HD resolution"),
            ResolutionPreset("4K UHD", 3840, 2160, PresetType.STANDARD,
                           description="4K Ultra HD resolution"),
            ResolutionPreset("5K", 5120, 2880, PresetType.STANDARD,
                           description="5K resolution"),
            
            # Gaming presets
            ResolutionPreset("Gaming 16:9", 1920, 1080, PresetType.GAMING,
                           description="Optimal gaming resolution"),
            ResolutionPreset("Gaming 21:9", 2560, 1080, PresetType.GAMING,
                           description="Ultra-wide gaming"),
            ResolutionPreset("Gaming 32:9", 3840, 1080, PresetType.GAMING,
                           description="Super ultra-wide gaming"),
            
            # Work presets
            ResolutionPreset("Work Window", 1200, 800, PresetType.WORK,
                           description="Comfortable work window"),
            ResolutionPreset("Code Editor", 1400, 900, PresetType.WORK,
                           description="Code editing window"),
            ResolutionPreset("Document View", 800, 1000, PresetType.WORK,
                           description="Document viewing"),
            
            # Media presets
            ResolutionPreset("Video Player", 1280, 720, PresetType.MEDIA,
                           description="Video playback window"),
            ResolutionPreset("Image Viewer", 1024, 768, PresetType.MEDIA,
                           description="Image viewing window"),
            ResolutionPreset("Media Center", 1920, 1080, PresetType.MEDIA,
                           description="Full media experience"),
        ]
        
        for preset in builtin_presets:
            self.presets[preset.name] = preset
    
    def _load_user_presets(self):
        """Load user-created presets."""
        try:
            presets_data = self.settings.value("user_presets", [])
            if isinstance(presets_data, list):
                for preset_data in presets_data:
                    if isinstance(preset_data, dict):
                        preset = ResolutionPreset.from_dict(preset_data)
                        self.presets[preset.name] = preset
        except Exception as e:
            logger.error(f"Error loading user presets: {e}")
    
    def _save_user_presets(self):
        """Save user-created presets."""
        try:
            user_presets = [
                preset.to_dict() for preset in self.presets.values()
                if preset.created_by_user
            ]
            self.settings.setValue("user_presets", user_presets)
        except Exception as e:
            logger.error(f"Error saving user presets: {e}")
    
    def add_preset(self, preset: ResolutionPreset) -> bool:
        """Add a new preset."""
        if preset.name in self.presets and not self.presets[preset.name].created_by_user:
            # Cannot override built-in presets
            return False
        
        self.presets[preset.name] = preset
        if preset.created_by_user:
            self._save_user_presets()
        
        self.presets_changed.emit()
        logger.info(f"Added preset: {preset.name}")
        return True
    
    def remove_preset(self, name: str) -> bool:
        """Remove a preset."""
        if name not in self.presets:
            return False
        
        preset = self.presets[name]
        if not preset.created_by_user:
            # Cannot remove built-in presets
            return False
        
        del self.presets[name]
        self._save_user_presets()
        self.presets_changed.emit()
        logger.info(f"Removed preset: {name}")
        return True
    
    def get_presets_by_type(self, preset_type: PresetType) -> List[ResolutionPreset]:
        """Get presets by type."""
        return [preset for preset in self.presets.values() 
                if preset.preset_type == preset_type]
    
    def get_all_presets(self) -> List[ResolutionPreset]:
        """Get all presets sorted by usage count."""
        return sorted(self.presets.values(), 
                     key=lambda x: x.usage_count, reverse=True)
    
    def apply_preset(self, name: str, hwnd: int) -> bool:
        """Apply preset to window."""
        if name not in self.presets or not WIN32_AVAILABLE:
            return False
        
        preset = self.presets[name]
        
        try:
            # Get current window rect for positioning
            current_rect = win32gui.GetWindowRect(hwnd)
            
            # Calculate position based on preset
            x, y = self._calculate_position(preset.position, preset.width, preset.height)
            
            # Apply the size and position
            success = win32gui.SetWindowPos(
                hwnd, 0, x, y, preset.width, preset.height,
                win32con.SWP_NOZORDER
            )
            
            if success:
                # Update usage count
                preset.usage_count += 1
                if preset.created_by_user:
                    self._save_user_presets()
                
                self.preset_applied.emit(preset.name, preset.width, preset.height)
                logger.info(f"Applied preset '{name}' to window {hwnd}")
                return True
            
        except Exception as e:
            logger.error(f"Error applying preset '{name}': {e}")
        
        return False
    
    def _calculate_position(self, position: PositionPreset, width: int, height: int) -> Tuple[int, int]:
        """Calculate window position based on preset."""
        if not WIN32_AVAILABLE:
            return (100, 100)
        
        try:
            # Get screen dimensions
            screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            
            if position == PositionPreset.CENTER:
                x = (screen_width - width) // 2
                y = (screen_height - height) // 2
            elif position == PositionPreset.TOP_LEFT:
                x, y = 0, 0
            elif position == PositionPreset.TOP_RIGHT:
                x, y = screen_width - width, 0
            elif position == PositionPreset.BOTTOM_LEFT:
                x, y = 0, screen_height - height
            elif position == PositionPreset.BOTTOM_RIGHT:
                x, y = screen_width - width, screen_height - height
            elif position == PositionPreset.LEFT_HALF:
                x, y = 0, 0
                # Override width to half screen
                width = screen_width // 2
            elif position == PositionPreset.RIGHT_HALF:
                x, y = screen_width // 2, 0
                # Override width to half screen
                width = screen_width // 2
            elif position == PositionPreset.TOP_HALF:
                x, y = 0, 0
                # Override height to half screen
                height = screen_height // 2
            elif position == PositionPreset.BOTTOM_HALF:
                x, y = 0, screen_height // 2
                # Override height to half screen
                height = screen_height // 2
            else:
                x, y = 100, 100  # Default position
            
            return (x, y)
            
        except Exception as e:
            logger.error(f"Error calculating position: {e}")
            return (100, 100)

class PresetControlsWidget(QWidget):
    """Widget containing preset resolution controls and window search."""
    
    preset_applied = pyqtSignal(str, int, int, int)  # name, width, height, hwnd
    window_selected = pyqtSignal(int)  # hwnd
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.preset_manager = PresetManager()
        self.search_thread = WindowSearchThread()
        self.current_results: List[WindowSearchResult] = []
        
        self._setup_ui()
        self._connect_signals()
        
        # Start initial search
        QTimer.singleShot(100, self._perform_search)
    
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Create tabbed interface
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # Preset tab
        preset_tab = self._create_preset_tab()
        tab_widget.addTab(preset_tab, "Presets")
        
        # Search tab
        search_tab = self._create_search_tab()
        tab_widget.addTab(search_tab, "Window Search")
        
        # Quick actions
        quick_actions = self._create_quick_actions()
        layout.addWidget(quick_actions)
    
    def _create_preset_tab(self) -> QWidget:
        """Create the preset resolution tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Preset type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Category:"))
        
        self.preset_type_combo = QComboBox()
        for preset_type in PresetType:
            self.preset_type_combo.addItem(preset_type.value.title(), preset_type)
        self.preset_type_combo.currentTextChanged.connect(self._update_preset_buttons)
        type_layout.addWidget(self.preset_type_combo)
        
        type_layout.addStretch()
        
        # Add custom preset button
        add_preset_btn = QPushButton("Add Custom")
        add_preset_btn.clicked.connect(self._show_add_preset_dialog)
        type_layout.addWidget(add_preset_btn)
        
        layout.addLayout(type_layout)
        
        # Preset buttons area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(300)
        
        self.preset_buttons_widget = QWidget()
        self.preset_buttons_layout = QGridLayout(self.preset_buttons_widget)
        scroll_area.setWidget(self.preset_buttons_widget)
        
        layout.addWidget(scroll_area)
        
        # Custom size controls
        custom_group = QGroupBox("Custom Size")
        custom_layout = QHBoxLayout(custom_group)
        
        custom_layout.addWidget(QLabel("Width:"))
        self.custom_width = QSpinBox()
        self.custom_width.setRange(100, 7680)
        self.custom_width.setValue(1920)
        custom_layout.addWidget(self.custom_width)
        
        custom_layout.addWidget(QLabel("Height:"))
        self.custom_height = QSpinBox()
        self.custom_height.setRange(100, 4320)
        self.custom_height.setValue(1080)
        custom_layout.addWidget(self.custom_height)
        
        apply_custom_btn = QPushButton("Apply Custom")
        apply_custom_btn.clicked.connect(self._apply_custom_size)
        custom_layout.addWidget(apply_custom_btn)
        
        layout.addWidget(custom_group)
        
        # Initialize preset buttons
        self._update_preset_buttons()
        
        return tab
    
    def _create_search_tab(self) -> QWidget:
        """Create the window search tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Search controls
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search windows by title, process, or class...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        search_layout.addWidget(self.search_input)
        
        self.visible_only_check = QCheckBox("Visible only")
        self.visible_only_check.setChecked(True)
        self.visible_only_check.toggled.connect(self._on_search_options_changed)
        search_layout.addWidget(self.visible_only_check)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._perform_search)
        search_layout.addWidget(refresh_btn)
        
        layout.addLayout(search_layout)
        
        # Results tree
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Title", "Process", "Class", "Size", "Visible"])
        self.results_tree.setRootIsDecorated(False)
        self.results_tree.setAlternatingRowColors(True)
        self.results_tree.setSortingEnabled(True)
        self.results_tree.itemDoubleClicked.connect(self._on_result_double_clicked)
        
        # Set column widths
        header = self.results_tree.header()
        header.resizeSection(0, 300)  # Title
        header.resizeSection(1, 150)  # Process
        header.resizeSection(2, 150)  # Class
        header.resizeSection(3, 100)  # Size
        header.resizeSection(4, 60)   # Visible
        
        layout.addWidget(self.results_tree)
        
        # Results info
        self.results_info = QLabel("No results")
        layout.addWidget(self.results_info)
        
        return tab
    
    def _create_quick_actions(self) -> QWidget:
        """Create quick action buttons."""
        group = QGroupBox("Quick Actions")
        layout = QHBoxLayout(group)
        
        # Common quick actions
        center_btn = QPushButton("Center Window")
        center_btn.clicked.connect(lambda: self._quick_action("center"))
        layout.addWidget(center_btn)
        
        maximize_btn = QPushButton("Maximize")
        maximize_btn.clicked.connect(lambda: self._quick_action("maximize"))
        layout.addWidget(maximize_btn)
        
        minimize_btn = QPushButton("Minimize")
        minimize_btn.clicked.connect(lambda: self._quick_action("minimize"))
        layout.addWidget(minimize_btn)
        
        layout.addStretch()
        
        return group
    
    def _connect_signals(self):
        """Connect signals."""
        self.preset_manager.presets_changed.connect(self._update_preset_buttons)
        self.preset_manager.preset_applied.connect(
            lambda name, w, h: self.preset_applied.emit(name, w, h, 0)
        )
        self.search_thread.results_ready.connect(self._on_search_results)
    
    def _update_preset_buttons(self):
        """Update preset buttons based on selected type."""
        # Clear existing buttons
        for i in reversed(range(self.preset_buttons_layout.count())):
            child = self.preset_buttons_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        # Get current preset type
        current_type = self.preset_type_combo.currentData()
        if not current_type:
            return
        
        # Get presets for current type
        presets = self.preset_manager.get_presets_by_type(current_type)
        
        # Create buttons in grid layout
        row, col = 0, 0
        max_cols = 3
        
        for preset in presets:
            btn = QPushButton(f"{preset.name}\n{preset.width}×{preset.height}")
            btn.setMinimumHeight(60)
            btn.setToolTip(preset.description)
            btn.clicked.connect(lambda checked, p=preset: self._apply_preset(p))
            
            self.preset_buttons_layout.addWidget(btn, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
    
    def _apply_preset(self, preset: ResolutionPreset):
        """Apply preset to selected window."""
        # For now, emit signal with window 0 (caller should handle window selection)
        self.preset_applied.emit(preset.name, preset.width, preset.height, 0)
    
    def _apply_custom_size(self):
        """Apply custom size."""
        width = self.custom_width.value()
        height = self.custom_height.value()
        self.preset_applied.emit("Custom", width, height, 0)
    
    def _on_search_text_changed(self):
        """Handle search text changes."""
        # Debounce search
        if hasattr(self, '_search_timer'):
            self._search_timer.stop()
        
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._perform_search)
        self._search_timer.start(300)  # 300ms delay
    
    def _on_search_options_changed(self):
        """Handle search option changes."""
        self._perform_search()
    
    def _perform_search(self):
        """Perform window search."""
        query = self.search_input.text()
        visible_only = self.visible_only_check.isChecked()
        
        self.search_thread.set_search_params(query, visible_only)
        
        if not self.search_thread.isRunning():
            self.search_thread.start()
    
    def _on_search_results(self, results: List[WindowSearchResult]):
        """Handle search results."""
        self.current_results = results
        
        # Clear tree
        self.results_tree.clear()
        
        # Add results
        for result in results:
            item = QTreeWidgetItem([
                result.title or "<No Title>",
                result.process_name,
                result.class_name,
                f"{result.rect[2] - result.rect[0]}×{result.rect[3] - result.rect[1]}",
                "Yes" if result.is_visible else "No"
            ])
            item.setData(0, Qt.UserRole, result.hwnd)
            self.results_tree.addTopLevelItem(item)
        
        # Update info
        self.results_info.setText(f"Found {len(results)} windows")
        
        # Sort by relevance (first column)
        self.results_tree.sortItems(0, Qt.DescendingOrder)

    def _on_result_double_clicked(self, item, column):
        """Handle double-click on search result."""
        hwnd = item.data(0, Qt.UserRole)
        if hwnd:
            self.window_selected.emit(hwnd)
    
    def _quick_action(self, action: str):
        """Perform quick action."""
        # Emit signal - caller should handle the action
        pass
    
    def _show_add_preset_dialog(self):
        """Show dialog to add custom preset."""
        # TODO: Implement custom preset dialog
        pass
    
    def set_selected_window(self, hwnd: int):
        """Set the currently selected window for preset application."""
        # Store for preset application
        self._selected_hwnd = hwnd
    
    def get_search_results(self) -> List[WindowSearchResult]:
        """Get current search results."""
        return self.current_results.copy()

if __name__ == "__main__":
    # Test preset controls
    import logging
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    logging.basicConfig(level=logging.INFO)
    
    app = QApplication(sys.argv)
    
    # Create test window
    window = QMainWindow()
    window.setWindowTitle("Preset Controls Test")
    window.resize(800, 600)
    
    # Create preset controls
    preset_controls = PresetControlsWidget()
    window.setCentralWidget(preset_controls)
    
    # Connect signals
    def on_preset_applied(name, width, height, hwnd):
        print(f"Preset applied: {name} ({width}×{height}) to window {hwnd}")
    
    def on_window_selected(hwnd):
        print(f"Window selected: {hwnd}")
    
    preset_controls.preset_applied.connect(on_preset_applied)
    preset_controls.window_selected.connect(on_window_selected)
    
    window.show()
    
    print("Preset controls test running...")
    sys.exit(app.exec_())