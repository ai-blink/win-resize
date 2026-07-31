"""
Profile Management Dialog
========================

PyQt5 dialog for managing window profiles with create, edit, delete,
and apply functionality.

Key Features:
- Profile list with search and filtering
- Create/Edit profile dialog
- Profile application and auto-apply settings
- Import/Export functionality
- Profile statistics and usage tracking
"""

import sys
import os
import time
from typing import Dict, List, Optional, Any
import logging

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel,
    QLineEdit, QTextEdit, QComboBox, QCheckBox, QSpinBox,
    QGroupBox, QTabWidget, QWidget, QMessageBox, QInputDialog,
    QFileDialog, QProgressDialog, QSplitter, QFrame,
    QDialogButtonBox, QFormLayout, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor

# Import profile management components
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.profile_manager import (
    ProfileManager, Profile, MatchingCriteria, WindowConfiguration,
    MatchingStrategy, ProfileType, default_profile_manager
)
from gui.theme_manager import get_theme_manager, ThemeElement

logger = logging.getLogger(__name__)


def create_themed_message_box_dialog(parent, icon, title, text, buttons=QMessageBox.Ok):
    """Create a message box with proper dark mode theming for profile dialog."""
    try:
        theme_manager = get_theme_manager()
        
        # Create message box
        msg_box = QMessageBox(parent)
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setStandardButtons(buttons)
        
        # Apply dark mode styling if needed
        if theme_manager.current_theme.value == 'dark':
            # Get dark theme colors
            bg_color = theme_manager.get_color_string(ThemeElement.FOREGROUND)
            text_color = theme_manager.get_color_string(ThemeElement.TEXT)
            button_color = theme_manager.get_color_string(ThemeElement.BUTTON)
            button_hover = theme_manager.get_color_string(ThemeElement.BUTTON_HOVER)
            accent_color = theme_manager.get_color_string(ThemeElement.ACCENT)
            border_color = theme_manager.get_color_string(ThemeElement.BORDER)
            
            # Apply enhanced styling for dark mode
            msg_box.setStyleSheet(f"""
                QMessageBox {{
                    background-color: {bg_color};
                    color: {text_color};
                    border: 2px solid {border_color};
                    border-radius: 8px;
                }}
                QMessageBox QLabel {{
                    background-color: {bg_color};
                    color: {text_color};
                    font-size: 12pt;
                    font-weight: 500;
                    padding: 15px;
                    border: none;
                }}
                QMessageBox QPushButton {{
                    background-color: {button_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    padding: 10px 20px;
                    color: {text_color};
                    font-weight: bold;
                    min-width: 80px;
                    min-height: 30px;
                    font-size: 10pt;
                }}
                QMessageBox QPushButton:hover {{
                    background-color: {button_hover};
                    border: 2px solid {accent_color};
                }}
                QMessageBox QPushButton:pressed {{
                    background-color: {accent_color};
                    color: {bg_color};
                }}
                QMessageBox QPushButton:default {{
                    background-color: {accent_color};
                    color: {bg_color};
                    border: 2px solid {accent_color};
                }}
            """)
        
        return msg_box
        
    except Exception as e:
        logger.error(f"Error creating themed message box: {e}")
        # Fallback to standard message box
        msg_box = QMessageBox(parent)
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setStandardButtons(buttons)
        return msg_box


def show_themed_dialog_message(parent, icon, title, text, buttons=QMessageBox.Ok):
    """Show a themed message box and return the result."""
    msg_box = create_themed_message_box_dialog(parent, icon, title, text, buttons)
    return msg_box.exec_()


def show_themed_dialog_information(parent, title, text):
    """Show a themed information message."""
    return show_themed_dialog_message(parent, QMessageBox.Information, title, text)


def show_themed_dialog_warning(parent, title, text):
    """Show a themed warning message."""
    return show_themed_dialog_message(parent, QMessageBox.Warning, title, text)


def show_themed_dialog_critical(parent, title, text):
    """Show a themed critical error message."""
    return show_themed_dialog_message(parent, QMessageBox.Critical, title, text)


def show_themed_dialog_question(parent, title, text):
    """Show a themed question message with Yes/No buttons."""
    return show_themed_dialog_message(parent, QMessageBox.Question, title, text, 
                                    QMessageBox.Yes | QMessageBox.No)

class ProfileEditDialog(QDialog):
    """Dialog for creating or editing a profile."""
    
    def __init__(self, parent=None, profile: Profile = None, window_info: Dict[str, Any] = None):
        """Initialize profile edit dialog."""
        super().__init__(parent)
        self.profile = profile
        self.window_info = window_info
        self.is_editing = profile is not None
        
        self.setup_ui()
        self.load_data()
        
        title = "프로필 편집" if self.is_editing else "프로필 생성"
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(500, 600)
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Create tab widget
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # Basic info tab
        basic_tab = self.create_basic_tab()
        tab_widget.addTab(basic_tab, "Basic Info")
        
        # Window config tab
        config_tab = self.create_config_tab()
        tab_widget.addTab(config_tab, "Window Config")
        
        # Matching criteria tab
        matching_tab = self.create_matching_tab()
        tab_widget.addTab(matching_tab, "Matching")
        
        # Settings tab
        settings_tab = self.create_settings_tab()
        tab_widget.addTab(settings_tab, "Settings")
        
        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def create_basic_tab(self) -> QWidget:
        """Create basic information tab."""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # Profile name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter profile name...")
        layout.addRow("Name:", self.name_edit)
        
        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setPlaceholderText("Optional description...")
        layout.addRow("Description:", self.description_edit)
        
        # Profile type
        self.type_combo = QComboBox()
        for ptype in ProfileType:
            self.type_combo.addItem(ptype.value.replace('_', ' ').title(), ptype)
        layout.addRow("Type:", self.type_combo)
        
        # Tags
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("comma, separated, tags")
        layout.addRow("Tags:", self.tags_edit)
        
        return widget
    
    def create_config_tab(self) -> QWidget:
        """Create window configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Position group
        pos_group = QGroupBox("Position")
        pos_layout = QGridLayout(pos_group)
        
        self.x_spinbox = QSpinBox()
        self.x_spinbox.setRange(-9999, 9999)
        self.x_spinbox.setSuffix(" px")
        pos_layout.addWidget(QLabel("X:"), 0, 0)
        pos_layout.addWidget(self.x_spinbox, 0, 1)
        
        self.y_spinbox = QSpinBox()
        self.y_spinbox.setRange(-9999, 9999)
        self.y_spinbox.setSuffix(" px")
        pos_layout.addWidget(QLabel("Y:"), 0, 2)
        pos_layout.addWidget(self.y_spinbox, 0, 3)
        
        layout.addWidget(pos_group)
        
        # Size group
        size_group = QGroupBox("Size")
        size_layout = QGridLayout(size_group)
        
        self.width_spinbox = QSpinBox()
        self.width_spinbox.setRange(1, 9999)
        self.width_spinbox.setSuffix(" px")
        size_layout.addWidget(QLabel("Width:"), 0, 0)
        size_layout.addWidget(self.width_spinbox, 0, 1)
        
        self.height_spinbox = QSpinBox()
        self.height_spinbox.setRange(1, 9999)
        self.height_spinbox.setSuffix(" px")
        size_layout.addWidget(QLabel("Height:"), 0, 2)
        size_layout.addWidget(self.height_spinbox, 0, 3)
        
        layout.addWidget(size_group)
        
        # State group
        state_group = QGroupBox("Window State")
        state_layout = QVBoxLayout(state_group)
        
        self.maximized_checkbox = QCheckBox("Maximized")
        state_layout.addWidget(self.maximized_checkbox)
        
        self.minimized_checkbox = QCheckBox("Minimized")
        state_layout.addWidget(self.minimized_checkbox)
        
        self.always_on_top_checkbox = QCheckBox("Always on Top")
        state_layout.addWidget(self.always_on_top_checkbox)
        
        layout.addWidget(state_group)
        
        # Use current window button
        if self.window_info:
            use_current_button = QPushButton("Use Current Window")
            use_current_button.clicked.connect(self.use_current_window)
            layout.addWidget(use_current_button)
        
        layout.addStretch()
        return widget
    
    def create_matching_tab(self) -> QWidget:
        """Create matching criteria tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Strategy selection
        strategy_group = QGroupBox("Matching Strategy")
        strategy_layout = QFormLayout(strategy_group)
        
        self.strategy_combo = QComboBox()
        for strategy in MatchingStrategy:
            self.strategy_combo.addItem(strategy.value.replace('_', ' ').title(), strategy)
        self.strategy_combo.currentTextChanged.connect(self.on_strategy_changed)
        strategy_layout.addRow("Strategy:", self.strategy_combo)
        
        layout.addWidget(strategy_group)
        
        # Patterns group
        patterns_group = QGroupBox("Matching Patterns")
        patterns_layout = QFormLayout(patterns_group)
        
        self.title_pattern_edit = QLineEdit()
        self.title_pattern_edit.setPlaceholderText("Window title pattern...")
        patterns_layout.addRow("Title Pattern:", self.title_pattern_edit)
        
        self.process_pattern_edit = QLineEdit()
        self.process_pattern_edit.setPlaceholderText("Process name pattern...")
        patterns_layout.addRow("Process Pattern:", self.process_pattern_edit)
        
        self.class_pattern_edit = QLineEdit()
        self.class_pattern_edit.setPlaceholderText("Window class pattern...")
        patterns_layout.addRow("Class Pattern:", self.class_pattern_edit)
        
        layout.addWidget(patterns_group)
        
        # Options group
        options_group = QGroupBox("Matching Options")
        options_layout = QVBoxLayout(options_group)
        
        self.case_sensitive_checkbox = QCheckBox("Case Sensitive")
        options_layout.addWidget(self.case_sensitive_checkbox)
        
        # Priority
        priority_layout = QHBoxLayout()
        priority_layout.addWidget(QLabel("Priority:"))
        self.priority_spinbox = QSpinBox()
        self.priority_spinbox.setRange(1, 100)
        self.priority_spinbox.setValue(50)
        priority_layout.addWidget(self.priority_spinbox)
        priority_layout.addStretch()
        options_layout.addLayout(priority_layout)
        
        layout.addWidget(options_group)
        
        # Use current window button
        if self.window_info:
            use_current_button = QPushButton("Use Current Window Info")
            use_current_button.clicked.connect(self.use_current_window_matching)
            layout.addWidget(use_current_button)
        
        layout.addStretch()
        return widget
    
    def create_settings_tab(self) -> QWidget:
        """Create settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Behavior group
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QVBoxLayout(behavior_group)
        
        self.auto_apply_checkbox = QCheckBox("Auto-apply when matching window is detected")
        behavior_layout.addWidget(self.auto_apply_checkbox)
        
        self.enabled_checkbox = QCheckBox("Profile enabled")
        self.enabled_checkbox.setChecked(True)
        behavior_layout.addWidget(self.enabled_checkbox)
        
        layout.addWidget(behavior_group)
        
        layout.addStretch()
        return widget
    
    def on_strategy_changed(self):
        """Handle strategy selection change."""
        strategy = self.strategy_combo.currentData()
        
        # Enable/disable relevant fields
        if strategy == MatchingStrategy.EXACT_TITLE:
            self.title_pattern_edit.setEnabled(True)
            self.process_pattern_edit.setEnabled(False)
            self.class_pattern_edit.setEnabled(False)
        elif strategy == MatchingStrategy.TITLE_CONTAINS:
            self.title_pattern_edit.setEnabled(True)
            self.process_pattern_edit.setEnabled(False)
            self.class_pattern_edit.setEnabled(False)
        elif strategy == MatchingStrategy.TITLE_REGEX:
            self.title_pattern_edit.setEnabled(True)
            self.process_pattern_edit.setEnabled(False)
            self.class_pattern_edit.setEnabled(False)
        elif strategy == MatchingStrategy.PROCESS_NAME:
            self.title_pattern_edit.setEnabled(False)
            self.process_pattern_edit.setEnabled(True)
            self.class_pattern_edit.setEnabled(False)
        elif strategy == MatchingStrategy.COMBINED:
            self.title_pattern_edit.setEnabled(True)
            self.process_pattern_edit.setEnabled(True)
            self.class_pattern_edit.setEnabled(True)
    
    def use_current_window(self):
        """Use current window configuration."""
        if not self.window_info or 'rect' not in self.window_info:
            return
        
        rect = self.window_info['rect']
        self.x_spinbox.setValue(rect.left)
        self.y_spinbox.setValue(rect.top)
        self.width_spinbox.setValue(rect.width)
        self.height_spinbox.setValue(rect.height)
        
        self.maximized_checkbox.setChecked(self.window_info.get('is_maximized', False))
        self.minimized_checkbox.setChecked(self.window_info.get('is_minimized', False))
    
    def use_current_window_matching(self):
        """Use current window info for matching."""
        if not self.window_info:
            return
        
        self.title_pattern_edit.setText(self.window_info.get('title', ''))
        self.process_pattern_edit.setText(self.window_info.get('process_name', ''))
        self.class_pattern_edit.setText(self.window_info.get('class_name', ''))
    
    def load_data(self):
        """Load data into form fields."""
        if not self.profile:
            # Set defaults for new profile
            if self.window_info:
                self.use_current_window()
                self.use_current_window_matching()
            return
        
        # Load existing profile data
        self.name_edit.setText(self.profile.name)
        self.description_edit.setPlainText(self.profile.description)
        
        # Set profile type
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == self.profile.profile_type:
                self.type_combo.setCurrentIndex(i)
                break
        
        # Set tags
        self.tags_edit.setText(', '.join(self.profile.tags))
        
        # Load window configuration
        if self.profile.window_config:
            config = self.profile.window_config
            self.x_spinbox.setValue(config.x)
            self.y_spinbox.setValue(config.y)
            self.width_spinbox.setValue(config.width)
            self.height_spinbox.setValue(config.height)
            self.maximized_checkbox.setChecked(config.is_maximized)
            self.minimized_checkbox.setChecked(config.is_minimized)
            self.always_on_top_checkbox.setChecked(config.always_on_top)
        
        # Load matching criteria
        if self.profile.matching_criteria:
            criteria = self.profile.matching_criteria
            
            # Set strategy
            for i in range(self.strategy_combo.count()):
                if self.strategy_combo.itemData(i) == criteria.strategy:
                    self.strategy_combo.setCurrentIndex(i)
                    break
            
            self.title_pattern_edit.setText(criteria.window_title_pattern or '')
            self.process_pattern_edit.setText(criteria.process_name_pattern or '')
            self.class_pattern_edit.setText(criteria.window_class_pattern or '')
            self.case_sensitive_checkbox.setChecked(criteria.case_sensitive)
            self.priority_spinbox.setValue(criteria.priority)
        
        # Load settings
        self.auto_apply_checkbox.setChecked(self.profile.auto_apply)
        self.enabled_checkbox.setChecked(self.profile.enabled)
    
    def get_profile_data(self) -> Dict[str, Any]:
        """Get profile data from form."""
        # Basic info
        name = self.name_edit.text().strip()
        description = self.description_edit.toPlainText().strip()
        profile_type = self.type_combo.currentData()
        tags = [tag.strip() for tag in self.tags_edit.text().split(',') if tag.strip()]
        
        # Window configuration
        window_config = WindowConfiguration(
            x=self.x_spinbox.value(),
            y=self.y_spinbox.value(),
            width=self.width_spinbox.value(),
            height=self.height_spinbox.value(),
            is_maximized=self.maximized_checkbox.isChecked(),
            is_minimized=self.minimized_checkbox.isChecked(),
            always_on_top=self.always_on_top_checkbox.isChecked()
        )
        
        # Matching criteria
        matching_criteria = MatchingCriteria(
            strategy=self.strategy_combo.currentData(),
            window_title_pattern=self.title_pattern_edit.text().strip() or None,
            process_name_pattern=self.process_pattern_edit.text().strip() or None,
            window_class_pattern=self.class_pattern_edit.text().strip() or None,
            case_sensitive=self.case_sensitive_checkbox.isChecked(),
            priority=self.priority_spinbox.value()
        )
        
        return {
            'name': name,
            'description': description,
            'profile_type': profile_type,
            'tags': tags,
            'window_config': window_config,
            'matching_criteria': matching_criteria,
            'auto_apply': self.auto_apply_checkbox.isChecked(),
            'enabled': self.enabled_checkbox.isChecked()
        }
    
    def accept(self):
        """Accept dialog with validation."""
        data = self.get_profile_data()
        
        # Validate required fields
        if not data['name']:
            show_themed_dialog_warning(self, "검증 오류", "프로필 이름은 필수입니다.")
            return
        
        if not data['window_config'].validate():
            show_themed_dialog_warning(self, "검증 오류", "창 구성이 올바르지 않습니다.")
            return
        
        # Check for duplicate names (if not editing)
        if not self.is_editing:
            existing = default_profile_manager.get_profile_by_name(data['name'])
            if existing:
                show_themed_dialog_warning(self, "Validation Error", 
                                  f"Profile with name '{data['name']}' already exists.")
                return
        
        super().accept()

class ProfileManagerDialog(QDialog):
    """Main profile management dialog."""
    
    profile_applied = pyqtSignal(str, dict)  # profile_id, window_info
    
    def __init__(self, parent=None):
        """Initialize profile manager dialog."""
        super().__init__(parent)
        self.profile_manager = default_profile_manager
        self.current_window_info = None
        
        self.setup_ui()
        self.refresh_profiles()
        
        self.setWindowTitle("Profile Manager")
        self.setModal(False)
        self.resize(800, 600)
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QHBoxLayout(self)
        
        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Left panel - Profile list
        self.create_profile_list_panel(splitter)
        
        # Right panel - Profile details and actions
        self.create_profile_details_panel(splitter)
        
        # Set splitter proportions
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
    
    def create_profile_list_panel(self, parent):
        """Create profile list panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Search and filter
        search_layout = QHBoxLayout()
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search profiles...")
        self.search_edit.textChanged.connect(self.filter_profiles)
        search_layout.addWidget(self.search_edit)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All Types", None)
        for ptype in ProfileType:
            self.filter_combo.addItem(ptype.value.replace('_', ' ').title(), ptype)
        self.filter_combo.currentTextChanged.connect(self.filter_profiles)
        search_layout.addWidget(self.filter_combo)
        
        layout.addLayout(search_layout)
        
        # Profile list
        self.profile_list = QListWidget()
        self.profile_list.itemSelectionChanged.connect(self.on_profile_selected)
        self.profile_list.itemDoubleClicked.connect(self.edit_profile)
        layout.addWidget(self.profile_list)
        
        # Profile count
        self.profile_count_label = QLabel("0 profiles")
        layout.addWidget(self.profile_count_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.new_button = QPushButton("New")
        self.new_button.clicked.connect(self.new_profile)
        button_layout.addWidget(self.new_button)
        
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self.edit_profile)
        self.edit_button.setEnabled(False)
        button_layout.addWidget(self.edit_button)
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_profile)
        self.delete_button.setEnabled(False)
        button_layout.addWidget(self.delete_button)
        
        layout.addLayout(button_layout)
        
        parent.addWidget(widget)
    
    def create_profile_details_panel(self, parent):
        """Create profile details panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Profile details
        details_group = QGroupBox("Profile Details")
        details_layout = QVBoxLayout(details_group)
        
        self.details_label = QLabel("Select a profile to view details")
        self.details_label.setWordWrap(True)
        self.details_label.setAlignment(Qt.AlignTop)
        details_layout.addWidget(self.details_label)
        
        layout.addWidget(details_group)
        
        # Actions
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        
        self.apply_button = QPushButton("Apply to Current Window")
        self.apply_button.clicked.connect(self.apply_profile)
        self.apply_button.setEnabled(False)
        actions_layout.addWidget(self.apply_button)
        
        self.auto_apply_all_button = QPushButton("Auto-Apply All Profiles")
        self.auto_apply_all_button.clicked.connect(self.auto_apply_all)
        actions_layout.addWidget(self.auto_apply_all_button)
        
        layout.addWidget(actions_group)
        
        # Import/Export
        io_group = QGroupBox("Import/Export")
        io_layout = QHBoxLayout(io_group)
        
        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self.import_profiles)
        io_layout.addWidget(self.import_button)
        
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export_profiles)
        io_layout.addWidget(self.export_button)
        
        layout.addWidget(io_group)
        
        # Statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_label = QLabel("Loading statistics...")
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_group)
        
        # Update statistics
        self.update_statistics()
        
        layout.addStretch()
        parent.addWidget(widget)
    
    def set_current_window_info(self, window_info: Dict[str, Any]):
        """Set current window info for profile operations."""
        self.current_window_info = window_info
        
        # Update apply button state
        selected_items = self.profile_list.selectedItems()
        self.apply_button.setEnabled(len(selected_items) > 0 and window_info is not None)
    
    def refresh_profiles(self):
        """Refresh the profile list."""
        self.profile_list.clear()
        
        profiles = self.profile_manager.list_profiles()
        
        for profile in profiles:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, profile.id)
            
            # Format display text
            status_indicators = []
            if profile.auto_apply:
                status_indicators.append("AUTO")
            if not profile.enabled:
                status_indicators.append("DISABLED")
            
            status_text = f" [{', '.join(status_indicators)}]" if status_indicators else ""
            display_text = f"{profile.name}{status_text}\n{profile.description[:50]}..." if profile.description else f"{profile.name}{status_text}"
            
            item.setText(display_text)
            
            # Set color based on status
            if not profile.enabled:
                item.setForeground(QColor("#6c757d"))  # Gray for disabled
            elif profile.auto_apply:
                item.setForeground(QColor("#28a745"))  # Green for auto-apply
            
            self.profile_list.addItem(item)
        
        # Update count
        self.profile_count_label.setText(f"{len(profiles)} profiles")
        
        # Update statistics
        self.update_statistics()
    
    def filter_profiles(self):
        """Filter profiles based on search and type."""
        search_text = self.search_edit.text().lower()
        filter_type = self.filter_combo.currentData()
        
        profiles = self.profile_manager.list_profiles()
        
        # Apply filters
        if search_text:
            profiles = [p for p in profiles if 
                       search_text in p.name.lower() or 
                       search_text in p.description.lower()]
        
        if filter_type:
            profiles = [p for p in profiles if p.profile_type == filter_type]
        
        # Update list
        self.profile_list.clear()
        
        for profile in profiles:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, profile.id)
            
            status_indicators = []
            if profile.auto_apply:
                status_indicators.append("AUTO")
            if not profile.enabled:
                status_indicators.append("DISABLED")
            
            status_text = f" [{', '.join(status_indicators)}]" if status_indicators else ""
            display_text = f"{profile.name}{status_text}\n{profile.description[:50]}..." if profile.description else f"{profile.name}{status_text}"
            
            item.setText(display_text)
            
            if not profile.enabled:
                item.setForeground(QColor("#6c757d"))
            elif profile.auto_apply:
                item.setForeground(QColor("#28a745"))
            
            self.profile_list.addItem(item)
        
        self.profile_count_label.setText(f"{len(profiles)} profiles")
    
    def on_profile_selected(self):
        """Handle profile selection."""
        selected_items = self.profile_list.selectedItems()
        
        if not selected_items:
            self.details_label.setText("Select a profile to view details")
            self.edit_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.apply_button.setEnabled(False)
            return
        
        profile_id = selected_items[0].data(Qt.UserRole)
        profile = self.profile_manager.get_profile(profile_id)
        
        if not profile:
            return
        
        # Update details
        details_text = f"<b>{profile.name}</b><br>"
        details_text += f"Type: {profile.profile_type.value.replace('_', ' ').title()}<br>"
        details_text += f"Created: {time.strftime('%Y-%m-%d %H:%M', time.localtime(profile.created_at))}<br>"
        details_text += f"Applied: {profile.applied_count} times<br>"
        details_text += f"Auto-apply: {'Yes' if profile.auto_apply else 'No'}<br>"
        details_text += f"Enabled: {'Yes' if profile.enabled else 'No'}<br><br>"
        
        if profile.description:
            details_text += f"Description: {profile.description}<br><br>"
        
        if profile.window_config:
            config = profile.window_config
            details_text += f"<b>Window Configuration:</b><br>"
            details_text += f"Position: ({config.x}, {config.y})<br>"
            details_text += f"Size: {config.width} × {config.height}<br>"
            if config.is_maximized:
                details_text += "State: Maximized<br>"
            elif config.is_minimized:
                details_text += "State: Minimized<br>"
            if config.always_on_top:
                details_text += "Always on top: Yes<br>"
            details_text += "<br>"
        
        if profile.matching_criteria:
            criteria = profile.matching_criteria
            details_text += f"<b>Matching Criteria:</b><br>"
            details_text += f"Strategy: {criteria.strategy.value.replace('_', ' ').title()}<br>"
            if criteria.window_title_pattern:
                details_text += f"Title pattern: {criteria.window_title_pattern}<br>"
            if criteria.process_name_pattern:
                details_text += f"Process pattern: {criteria.process_name_pattern}<br>"
            if criteria.window_class_pattern:
                details_text += f"Class pattern: {criteria.window_class_pattern}<br>"
            if criteria.executable_path_pattern:
                details_text += f"Executable path: {criteria.executable_path_pattern}<br>"
            details_text += f"Priority: {criteria.priority}<br>"
        
        if profile.tags:
            details_text += f"<br><b>Tags:</b> {', '.join(profile.tags)}"
        
        self.details_label.setText(details_text)
        
        # Enable buttons
        self.edit_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.apply_button.setEnabled(self.current_window_info is not None)
    
    def new_profile(self):
        """Create new profile."""
        dialog = ProfileEditDialog(self, window_info=self.current_window_info)
        
        if dialog.exec_() == QDialog.Accepted:
            try:
                data = dialog.get_profile_data()
                profile = self.profile_manager.create_profile(**data)
                self.refresh_profiles()
                
                show_themed_dialog_information(self, "성공", 
                                      f"프로필 '{profile.name}'을 성공적으로 생성했습니다.")
                
            except Exception as e:
                show_themed_dialog_critical(self, "오류", f"프로필 생성에 실패했습니다:\n{str(e)}")
    
    def edit_profile(self):
        """Edit selected profile."""
        selected_items = self.profile_list.selectedItems()
        if not selected_items:
            return
        
        profile_id = selected_items[0].data(Qt.UserRole)
        profile = self.profile_manager.get_profile(profile_id)
        
        if not profile:
            return
        
        dialog = ProfileEditDialog(self, profile=profile, window_info=self.current_window_info)
        
        if dialog.exec_() == QDialog.Accepted:
            try:
                data = dialog.get_profile_data()
                success = self.profile_manager.update_profile(profile_id, **data)
                
                if success:
                    self.refresh_profiles()
                    show_themed_dialog_information(self, "Success", 
                                          f"Profile '{data['name']}' updated successfully.")
                else:
                    show_themed_dialog_warning(self, "Error", "Failed to update profile.")
                
            except Exception as e:
                show_themed_dialog_critical(self, "Error", f"Failed to update profile:\n{str(e)}")
    
    def delete_profile(self):
        """Delete selected profile."""
        selected_items = self.profile_list.selectedItems()
        if not selected_items:
            return
        
        profile_id = selected_items[0].data(Qt.UserRole)
        profile = self.profile_manager.get_profile(profile_id)
        
        if not profile:
            return
        
        reply = show_themed_dialog_question(
            self, "Confirm Delete",
            f"Are you sure you want to delete profile '{profile.name}'?"
        )
        
        if reply == QMessageBox.Yes:
            success = self.profile_manager.delete_profile(profile_id)
            
            if success:
                self.refresh_profiles()
                show_themed_dialog_information(self, "Success", "Profile deleted successfully.")
            else:
                show_themed_dialog_warning(self, "Error", "Failed to delete profile.")
    
    def apply_profile(self):
        """Apply selected profile to current window."""
        selected_items = self.profile_list.selectedItems()
        if not selected_items or not self.current_window_info:
            return
        
        profile_id = selected_items[0].data(Qt.UserRole)
        profile = self.profile_manager.get_profile(profile_id)
        
        if not profile:
            return
        
        try:
            success = self.profile_manager.apply_profile(profile_id, self.current_window_info)
            
            if success:
                self.profile_applied.emit(profile_id, self.current_window_info)
                self.refresh_profiles()  # Update statistics
                show_themed_dialog_information(self, "성공", 
                                      f"프로필 '{profile.name}'을 성공적으로 적용했습니다.")
            else:
                show_themed_dialog_warning(self, "오류", "프로필 적용에 실패했습니다.")
                
        except Exception as e:
            show_themed_dialog_critical(self, "오류", f"프로필 적용 중 오류가 발생했습니다:\n{str(e)}")
    
    def auto_apply_all(self):
        """Auto-apply all matching profiles."""
        # This would need window list from main application
        show_themed_dialog_information(self, "Info", 
                              "Auto-apply functionality requires integration with main window.")
    
    def import_profiles(self):
        """Import profiles from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Profiles", "", "JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            imported, skipped = self.profile_manager.import_profiles(file_path)
            self.refresh_profiles()
            
            show_themed_dialog_information(self, "Import Complete", 
                                  f"Imported {imported} profiles, skipped {skipped}.")
            
        except Exception as e:
            show_themed_dialog_critical(self, "Import Error", f"Failed to import profiles:\n{str(e)}")
    
    def export_profiles(self):
        """Export profiles to file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Profiles", "profiles.json", "JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            success = self.profile_manager.export_profiles(file_path)
            
            if success:
                show_themed_dialog_information(self, "Export Complete", 
                                      f"Profiles exported to {file_path}")
            else:
                show_themed_dialog_warning(self, "Export Error", "Failed to export profiles.")
                
        except Exception as e:
            show_themed_dialog_critical(self, "Export Error", f"Failed to export profiles:\n{str(e)}")
    
    def update_statistics(self):
        """Update profile statistics display."""
        try:
            stats = self.profile_manager.get_statistics()
            
            stats_text = f"Total Profiles: {stats['total']}<br>"
            stats_text += f"Enabled: {stats['enabled']}<br>"
            stats_text += f"Auto-apply: {stats['auto_apply']}<br>"
            stats_text += f"Total Applications: {stats['total_applications']}<br>"
            
            if stats.get('most_used_profile'):
                stats_text += f"<br>Most Used: {stats['most_used_profile']} ({stats['most_used_count']} times)"
            
            if stats.get('type_distribution'):
                stats_text += "<br><br>Types:<br>"
                for ptype, count in stats['type_distribution'].items():
                    stats_text += f"  {ptype.replace('_', ' ').title()}: {count}<br>"
            
            self.stats_label.setText(stats_text)
            
        except Exception as e:
            self.stats_label.setText(f"Error loading statistics: {e}")

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    dialog = ProfileManagerDialog()
    dialog.show()
    
    sys.exit(app.exec_())
