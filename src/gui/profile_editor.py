"""
Profile Editor Dialog
===================

Comprehensive profile editing dialog with hotkey configuration and advanced features.
"""

import sys
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, 
    QLabel, QLineEdit, QSpinBox, QCheckBox, QPushButton, QComboBox,
    QMessageBox, QTabWidget, QWidget, QFormLayout, QTextEdit, QScrollArea,
    QButtonGroup, QRadioButton
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QKeySequence

from core.profile_manager import Profile, WindowConfiguration, MatchingCriteria, MatchingStrategy, ProfileType
from gui.theme_manager import get_theme_manager, ThemeElement
from gui.ui_scale_manager import get_ui_scale_manager

logger = logging.getLogger(__name__)


def create_themed_message_box(parent, icon, title, text, buttons=QMessageBox.Ok):
    """Create a message box with proper dark mode theming."""
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
            msg_box.setStyleSheet(get_ui_scale_manager().scale_stylesheet(f"""
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
            """))
        
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


def show_themed_message(parent, icon, title, text, buttons=QMessageBox.Ok):
    """Show a themed message box and return the result."""
    msg_box = create_themed_message_box(parent, icon, title, text, buttons)
    return msg_box.exec_()


def show_themed_information(parent, title, text):
    """Show a themed information message."""
    return show_themed_message(parent, QMessageBox.Information, title, text)


def show_themed_warning(parent, title, text):
    """Show a themed warning message."""
    return show_themed_message(parent, QMessageBox.Warning, title, text)


def show_themed_critical(parent, title, text):
    """Show a themed critical error message."""
    return show_themed_message(parent, QMessageBox.Critical, title, text)


def show_themed_question(parent, title, text):
    """Show a themed question message with Yes/No buttons."""
    return show_themed_message(parent, QMessageBox.Question, title, text, 
                              QMessageBox.Yes | QMessageBox.No)


class HotkeyWidget(QWidget):
    """Widget for selecting hotkey combinations."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.current_keys = []
        
    def setup_ui(self):
        """Setup the hotkey selection UI."""
        layout = QHBoxLayout(self)
        layout.setSpacing(5)
        
        # 첫 번째 수식키 (Modifier 1)
        self.modifier1_combo = QComboBox()
        self.modifier1_combo.addItems(["없음", "Ctrl", "Alt", "Shift", "Win"])
        layout.addWidget(QLabel("수식키1:"))
        layout.addWidget(self.modifier1_combo)
        
        layout.addWidget(QLabel("+"))
        
        # 두 번째 수식키 (Modifier 2)
        self.modifier2_combo = QComboBox()
        self.modifier2_combo.addItems(["없음", "Ctrl", "Alt", "Shift", "Win"])
        layout.addWidget(QLabel("수식키2:"))
        layout.addWidget(self.modifier2_combo)
        
        layout.addWidget(QLabel("+"))
        
        # 메인 키
        self.main_key_combo = QComboBox()
        main_keys = ["선택하세요"]
        
        # 숫자 키
        main_keys.extend([str(i) for i in range(10)])
        
        # 알파벳 키
        main_keys.extend([chr(i) for i in range(ord('A'), ord('Z') + 1)])
        
        # 기능 키
        main_keys.extend([f"F{i}" for i in range(1, 13)])
        
        # 특수 키
        special_keys = [
            "Space", "Enter", "Tab", "Backspace", "Delete", 
            "Home", "End", "Page Up", "Page Down",
            "Left", "Right", "Up", "Down",
            "Insert", "Escape"
        ]
        main_keys.extend(special_keys)
        
        self.main_key_combo.addItems(main_keys)
        layout.addWidget(QLabel("메인키:"))
        layout.addWidget(self.main_key_combo)
        
        # 테스트 버튼
        self.test_button = QPushButton("테스트")
        self.test_button.setToolTip("단축키 조합을 테스트합니다")
        layout.addWidget(self.test_button)
        
        # 연결
        self.test_button.clicked.connect(self.test_hotkey)
        
    def test_hotkey(self):
        """Test the current hotkey combination."""
        combo = self.get_hotkey_string()
        if combo and combo != "":
            show_themed_information(self, "단축키 테스트", f"설정된 단축키: {combo}")
        else:
            show_themed_warning(self, "단축키 테스트", "메인키를 선택해주세요.")
    
    def get_hotkey_string(self) -> str:
        """Get the hotkey combination as a string."""
        keys = []
        
        if self.modifier1_combo.currentText() != "없음":
            keys.append(self.modifier1_combo.currentText())
            
        if self.modifier2_combo.currentText() != "없음":
            keys.append(self.modifier2_combo.currentText())
            
        if self.main_key_combo.currentText() != "선택하세요":
            keys.append(self.main_key_combo.currentText())
        
        return " + ".join(keys)
    
    def set_hotkey_string(self, hotkey_str: str):
        """Set the hotkey combination from a string."""
        if not hotkey_str:
            return
            
        keys = [k.strip() for k in hotkey_str.split('+')]
        
        # Reset combos
        self.modifier1_combo.setCurrentText("없음")
        self.modifier2_combo.setCurrentText("없음")
        self.main_key_combo.setCurrentText("선택하세요")
        
        modifiers = ["Ctrl", "Alt", "Shift", "Win"]
        main_keys_found = []
        
        for key in keys:
            if key in modifiers:
                if self.modifier1_combo.currentText() == "없음":
                    self.modifier1_combo.setCurrentText(key)
                elif self.modifier2_combo.currentText() == "없음":
                    self.modifier2_combo.setCurrentText(key)
            else:
                main_keys_found.append(key)
        
        # 메인키는 마지막 하나만 사용
        if main_keys_found:
            self.main_key_combo.setCurrentText(main_keys_found[-1])


class ProfileEditorDialog(QDialog):
    """Comprehensive profile editing dialog."""
    
    profile_saved = pyqtSignal(dict)  # 프로필 저장 시그널
    
    def __init__(self, profile: Profile = None, parent=None, window_info=None,
                 save_handler=None):
        super().__init__(parent)
        self.profile = profile
        self.window_info = window_info
        self.save_handler = save_handler
        self.is_new_profile = profile is None
        
        # Initialize theme manager
        self.theme_manager = get_theme_manager()
        self.ui_scale_manager = get_ui_scale_manager()
        
        self.setWindowTitle("프로필 편집" if profile else "새 프로필")
        self.setMinimumSize(600, 700)
        self.setModal(True)
        
        self.setup_ui()
        self.theme_manager.theme_changed.connect(self.apply_theme_styling)
        self.apply_theme_styling()  # Apply theme after UI setup
        
        if profile:
            self.load_profile_data()
        elif window_info:
            self.populate_from_window_info(window_info)

        self.ui_scale_manager.register_window(self)
        self.ui_scale_manager.scale_changed.connect(self.apply_ui_scale)
        self.apply_ui_scale(self.ui_scale_manager.scale_percent)
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Create tab widget for different sections
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 기본 정보 탭
        self.create_basic_info_tab()
        
        # 창 설정 탭
        self.create_window_settings_tab()
        
        # 단축키 설정 탭
        self.create_hotkey_tab()
        
        # 부가 기능 탭
        self.create_advanced_features_tab()
        
        # 자동 갱신 탭
        
        # 버튼 영역
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("저장")
        self.save_button.clicked.connect(self.save_profile)
        button_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def create_basic_info_tab(self):
        """Create basic information tab."""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # 프로필 이름
        self.name_edit = QLineEdit()
        self.name_edit.setToolTip("프로필의 이름을 입력하세요")
        layout.addRow("프로필명:", self.name_edit)
        
        # 설명
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setToolTip("프로필에 대한 설명을 입력하세요")
        layout.addRow("설명:", self.description_edit)
        
        # 프로필 타입
        self.profile_type_combo = QComboBox()
        self.profile_type_combo.addItems([
            "창 설정",
            "레이아웃", 
            "응용 프로그램",
            "작업공간"
        ])
        layout.addRow("프로필 타입:", self.profile_type_combo)
        
        
        # 프로필 활성화
        self.enabled_check = QCheckBox("프로필 활성화")
        self.enabled_check.setChecked(True)
        self.enabled_check.setToolTip("이 프로필의 사용 여부를 설정합니다")
        layout.addRow("", self.enabled_check)
        
        # 새 창 감지와 적용 뒤 위치/크기 유지
        self.auto_apply_check = QCheckBox("새 창 감지 및 실시간 위치/크기 유지")
        self.auto_apply_check.setToolTip(
            "켜면 이 프로필이 적용된 창의 위치와 크기를 계속 유지합니다. "
            "새 창에도 적용하려면 메인 화면에서 자동 감지를 켜세요."
        )
        layout.addRow("", self.auto_apply_check)
        
        self.tab_widget.addTab(tab, "기본 정보")
    
    def create_window_settings_tab(self):
        """Create window settings tab."""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        tab_layout.addWidget(scroll_area)

        content = QWidget()
        self.window_settings_content = content
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        scroll_area.setWidget(content)
        
        # 창 매칭 설정
        matching_group = QGroupBox("창 매칭 설정")
        matching_layout = QFormLayout(matching_group)
        
        # 매칭 전략
        self.matching_strategy_combo = QComboBox()
        self.matching_strategy_combo.addItem("창 제목 포함", "title_contains")
        self.matching_strategy_combo.addItem("창 제목 정확히 일치", "exact_title")
        self.matching_strategy_combo.addItem("정규식 매칭", "title_regex")
        self.matching_strategy_combo.addItem("프로세스 이름", "process_name")
        self.matching_strategy_combo.addItem("실행 파일 경로 (권장)", "executable_path")
        self.matching_strategy_combo.addItem("종합 매칭", "combined")
        matching_layout.addRow("매칭 방식:", self.matching_strategy_combo)

        self.matching_help_label = QLabel()
        self.matching_help_label.setWordWrap(True)
        self.matching_help_label.setStyleSheet("font-size: 11px;")
        matching_layout.addRow("", self.matching_help_label)
        
        # 창 제목 패턴
        self.window_title_edit = QLineEdit()
        self.window_title_edit.setToolTip("매칭할 창 제목이나 패턴을 입력하세요")
        matching_layout.addRow("창 제목 패턴:", self.window_title_edit)
        
        # 프로세스 이름 패턴  
        self.process_name_edit = QLineEdit()
        self.process_name_edit.setToolTip("매칭할 프로세스 이름을 입력하세요")
        matching_layout.addRow("프로세스 이름:", self.process_name_edit)

        self.executable_path_edit = QLineEdit()
        self.executable_path_edit.setPlaceholderText("예: C:\\Program Files\\App\\App.exe")
        self.executable_path_edit.setToolTip(
            "프로그램을 다시 실행해도 유지되는 전체 실행 파일 경로입니다"
        )
        self.executable_path_button = QPushButton("현재 창에서 가져오기")
        self.executable_path_button.setToolTip(
            "메인 화면에서 선택한 창의 실행 파일 경로를 채웁니다"
        )
        self.executable_path_button.clicked.connect(self.populate_executable_path)
        executable_path_layout = QHBoxLayout()
        executable_path_layout.setContentsMargins(0, 0, 0, 0)
        executable_path_layout.addWidget(self.executable_path_edit)
        executable_path_layout.addWidget(self.executable_path_button)
        matching_layout.addRow("실행 파일 경로:", executable_path_layout)
        
        # 대소문자 구분
        self.case_sensitive_check = QCheckBox("대소문자 구분")
        matching_layout.addRow("", self.case_sensitive_check)
        
        # 우선순위
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 100)
        self.priority_spin.setValue(50)
        self.priority_spin.setToolTip("프로필 적용 우선순위 (높을수록 우선)")
        matching_layout.addRow("우선순위:", self.priority_spin)

        self.matching_strategy_combo.currentIndexChanged.connect(
            self.update_matching_controls
        )
        self.update_matching_controls()
        
        layout.addWidget(matching_group)
        
        # 창 위치 및 크기 설정
        position_group = QGroupBox("창 위치 및 크기")
        position_layout = QVBoxLayout(position_group)
        
        # 위치/크기 입력 그리드
        input_layout = QGridLayout()
        
        # X, Y 좌표 - 간격 줄이기
        input_layout.addWidget(QLabel("X:"), 0, 0)
        self.x_spin = QSpinBox()
        self.x_spin.setRange(-9999, 9999)
        self.x_spin.setSuffix(" px")
        self.x_spin.setMaximumWidth(100)
        input_layout.addWidget(self.x_spin, 0, 1)
        
        input_layout.addWidget(QLabel("Y:"), 0, 2)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(-9999, 9999) 
        self.y_spin.setSuffix(" px")
        self.y_spin.setMaximumWidth(100)
        input_layout.addWidget(self.y_spin, 0, 3)
        
        # 위치 가져오기 버튼
        self.get_position_button = QPushButton("위치 가져오기")
        self.get_position_button.setToolTip("현재 선택된 창의 위치를 가져옵니다")
        self.get_position_button.clicked.connect(self.get_current_window_position)
        input_layout.addWidget(self.get_position_button, 0, 4)
        
        # 너비, 높이 - 간격 줄이기
        input_layout.addWidget(QLabel("폭:"), 1, 0)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 9999)
        self.width_spin.setSuffix(" px")
        self.width_spin.setMaximumWidth(100)
        input_layout.addWidget(self.width_spin, 1, 1)
        
        input_layout.addWidget(QLabel("높이:"), 1, 2)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 9999)
        self.height_spin.setSuffix(" px")
        self.height_spin.setMaximumWidth(100)
        input_layout.addWidget(self.height_spin, 1, 3)
        
        # 크기 가져오기 버튼
        self.get_size_button = QPushButton("크기 가져오기")
        self.get_size_button.setToolTip("현재 선택된 창의 크기를 가져옵니다")
        self.get_size_button.clicked.connect(self.get_current_window_size)
        input_layout.addWidget(self.get_size_button, 1, 4)
        
        position_layout.addLayout(input_layout)
        
        # 해상도 프리셋 버튼들
        resolution_group = QGroupBox("해상도 프리셋")
        resolution_layout = QHBoxLayout(resolution_group)
        
        self.fhd_button = QPushButton("FHD (1920x1080)")
        self.fhd_button.clicked.connect(lambda: self.set_resolution(1920, 1080))
        resolution_layout.addWidget(self.fhd_button)
        
        self.qhd_button = QPushButton("QHD (2560x1440)")
        self.qhd_button.clicked.connect(lambda: self.set_resolution(2560, 1440))
        resolution_layout.addWidget(self.qhd_button)
        
        self.uhd_button = QPushButton("UHD (3840x2160)")
        self.uhd_button.clicked.connect(lambda: self.set_resolution(3840, 2160))
        resolution_layout.addWidget(self.uhd_button)
        
        position_layout.addWidget(resolution_group)
        
        # 위치 프리셋 버튼들
        position_preset_group = QGroupBox("위치 프리셋")
        position_preset_layout = QGridLayout(position_preset_group)
        
        self.center_button = QPushButton("화면 중앙")
        self.center_button.clicked.connect(self.center_window)
        position_preset_layout.addWidget(self.center_button, 1, 1)
        
        self.top_button = QPushButton("위")
        self.top_button.clicked.connect(lambda: self.set_position_preset("top"))
        position_preset_layout.addWidget(self.top_button, 0, 1)
        
        self.bottom_button = QPushButton("아래")
        self.bottom_button.clicked.connect(lambda: self.set_position_preset("bottom"))
        position_preset_layout.addWidget(self.bottom_button, 2, 1)
        
        self.left_button = QPushButton("왼쪽")
        self.left_button.clicked.connect(lambda: self.set_position_preset("left"))
        position_preset_layout.addWidget(self.left_button, 1, 0)
        
        self.right_button = QPushButton("오른쪽")
        self.right_button.clicked.connect(lambda: self.set_position_preset("right"))
        position_preset_layout.addWidget(self.right_button, 1, 2)
        
        position_layout.addWidget(position_preset_group)
        
        # 창 상태
        state_layout = QHBoxLayout()
        
        self.maximized_check = QCheckBox("최대화")
        state_layout.addWidget(self.maximized_check)
        
        self.minimized_check = QCheckBox("최소화")
        state_layout.addWidget(self.minimized_check)
        
        self.always_on_top_check = QCheckBox("항상 위")
        state_layout.addWidget(self.always_on_top_check)
        
        state_layout.addStretch()  # Push checkboxes to left
        
        position_layout.addLayout(state_layout)

        position_lock_group = QGroupBox("창 이동 고정")
        position_lock_layout = QVBoxLayout(position_lock_group)

        self.lock_position_check = QCheckBox("창 위치 고정")
        self.lock_position_check.setToolTip(
            "활성화하면 프로필 적용 뒤 창을 이동해도 저장된 위치로 되돌립니다"
        )
        position_lock_layout.addWidget(self.lock_position_check)

        position_layout.addWidget(position_lock_group)
        
        layout.addWidget(position_group)
        
        self.tab_widget.addTab(tab, "창 설정")

    def populate_from_window_info(self, window_info):
        """Fill a new profile form from the selected main-window entry."""
        def value(name, default=None):
            if isinstance(window_info, dict):
                return window_info.get(name, default)
            return getattr(window_info, name, default)

        rect = value("rect")
        title = value("title", "")
        process_name = value("process_name", "")
        executable_path = value("executable_path", "")

        if title:
            self.name_edit.setText(f"{title} 프로필")
            self.description_edit.setPlainText(f"선택한 창에서 생성됨: {title}")
            self.window_title_edit.setText(title)
        if process_name:
            self.process_name_edit.setText(process_name)
        if executable_path:
            self.executable_path_edit.setText(executable_path)

        if rect:
            self.x_spin.setValue(rect.left)
            self.y_spin.setValue(rect.top)
            self.width_spin.setValue(rect.width)
            self.height_spin.setValue(rect.height)

        preferred_strategy = "executable_path" if executable_path else "process_name"
        strategy_index = self.matching_strategy_combo.findData(preferred_strategy)
        if strategy_index >= 0:
            self.matching_strategy_combo.setCurrentIndex(strategy_index)

    def update_matching_controls(self):
        """Keep the active matching inputs clear and focused for the user."""
        strategy = self.matching_strategy_combo.currentData()
        uses_title = strategy in ('title_contains', 'exact_title', 'title_regex', 'combined')
        uses_process = strategy in ('process_name', 'combined')
        uses_path = strategy in ('executable_path', 'combined')

        self.window_title_edit.setEnabled(uses_title)
        self.process_name_edit.setEnabled(uses_process)
        self.executable_path_edit.setEnabled(uses_path)
        self.executable_path_button.setEnabled(uses_path)

        help_messages = {
            'title_contains': '창 제목 일부로 찾습니다. 문서명처럼 제목이 자주 바뀌는 창에는 적합하지 않습니다.',
            'exact_title': '창 제목이 완전히 같을 때만 적용합니다.',
            'title_regex': '고급 설정입니다. 정규식과 일치하는 창 제목에만 적용합니다.',
            'process_name': '프로세스 파일명으로 찾습니다. 같은 이름의 다른 프로그램은 구분하지 못할 수 있습니다.',
            'executable_path': '권장 방식입니다. 실행 파일의 전체 경로로 구분하므로 재실행 후에도 유지됩니다. PID는 재실행마다 바뀌어 사용하지 않습니다.',
            'combined': '입력한 모든 조건이 일치해야 적용합니다. 필요한 조건만 채우세요.'
        }
        self.matching_help_label.setText(help_messages.get(strategy, ''))

    def populate_executable_path(self):
        """Fill the executable path from the selected window when available."""
        executable_path = ''
        current_window = getattr(self.parent(), 'current_window', None)
        if current_window:
            executable_path = getattr(current_window, 'executable_path', '')
            if not executable_path and getattr(current_window, 'pid', 0):
                try:
                    import psutil
                    executable_path = psutil.Process(current_window.pid).exe()
                except Exception as error:
                    logger.debug(f"Could not read selected window executable path: {error}")

        if not executable_path:
            show_themed_warning(
                self,
                "실행 파일 경로",
                "메인 화면에서 대상 창을 선택한 뒤 다시 시도해주세요."
            )
            return

        self.executable_path_edit.setText(executable_path)
        path_index = self.matching_strategy_combo.findData('executable_path')
        if path_index >= 0:
            self.matching_strategy_combo.setCurrentIndex(path_index)
    
    def create_hotkey_tab(self):
        """Create hotkey configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 단축키 설정 그룹
        hotkey_group = QGroupBox("단축키 설정")
        hotkey_layout = QVBoxLayout(hotkey_group)
        
        # 단축키 활성화 (전체)
        self.hotkey_enabled_check = QCheckBox("단축키 활성화")
        self.hotkey_enabled_check.setToolTip("이 프로필에 대한 단축키를 활성화합니다")
        hotkey_layout.addWidget(self.hotkey_enabled_check)
        
        # 단축키 세트들 (최대 3개)
        self.hotkey_sets = []
        for i in range(3):
            set_group = QGroupBox(f"단축키 세트 {i+1}")
            set_layout = QVBoxLayout(set_group)
            
            # 이 세트 활성화
            set_enabled = QCheckBox(f"세트 {i+1} 사용")
            set_layout.addWidget(set_enabled)
            
            # 키 조합 (3개 키)
            key_widget = HotkeyWidget()
            set_layout.addWidget(key_widget)
            
            # 동작 선택
            action_combo = QComboBox()
            action_combo.addItems([
                "프로필 적용",
                "프로필 해제", 
                "항상 위 토글",
                "자동 적용 토글"
            ])
            action_combo.setToolTip("이 단축키 조합이 실행할 동작을 선택합니다")
            set_layout.addWidget(QLabel("동작:"))
            set_layout.addWidget(action_combo)
            
            hotkey_set = {
                'enabled': set_enabled,
                'keys': key_widget,
                'action': action_combo
            }
            self.hotkey_sets.append(hotkey_set)
            hotkey_layout.addWidget(set_group)
        layout.addWidget(hotkey_group)
        
        self.tab_widget.addTab(tab, "단축키 설정")
    
    def create_advanced_features_tab(self):
        """Create advanced features tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        
        # 마우스 가둠 설정
        mouse_constraint_group = QGroupBox("마우스 창 안에 가두기")
        mouse_constraint_layout = QVBoxLayout(mouse_constraint_group)
        
        self.mouse_constraint_check = QCheckBox("마우스 가둠 활성화")
        self.mouse_constraint_check.setToolTip("마우스가 이 창 밖으로 나가지 못하게 합니다")
        mouse_constraint_layout.addWidget(self.mouse_constraint_check)
        
        
        # 해제 키 설정 (3키 조합 지원)
        exception_layout = QVBoxLayout()
        exception_layout.addWidget(QLabel("해제 키 조합:"))
        
        self.constraint_escape_widget = HotkeyWidget()
        self.constraint_escape_widget.setToolTip("마우스 가둠을 일시적으로 해제할 키 조합 (3키 조합 가능)")
        exception_layout.addWidget(self.constraint_escape_widget)
        
        mouse_constraint_layout.addLayout(exception_layout)
        layout.addWidget(mouse_constraint_group)
        
        # 고급 옵션
        advanced_group = QGroupBox("고급 옵션")
        advanced_layout = QFormLayout(advanced_group)
        
        # 투명도
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(0, 100)  # 0%부터 100%까지
        self.opacity_spin.setValue(0)  # 기본값 0% (완전 불투명)
        self.opacity_spin.setSuffix(" %")
        self.opacity_spin.setToolTip("창의 투명도를 설정합니다 (0%=불투명, 100%=완전투명)")
        advanced_layout.addRow("투명도:", self.opacity_spin)
        
        # 모니터 인덱스
        self.monitor_index_spin = QSpinBox()
        self.monitor_index_spin.setRange(0, 9)
        self.monitor_index_spin.setValue(0)
        self.monitor_index_spin.setToolTip("창이 표시될 모니터를 지정합니다")
        advanced_layout.addRow("모니터 번호:", self.monitor_index_spin)
        
        layout.addWidget(advanced_group)
        
        self.tab_widget.addTab(tab, "부가 기능")
    
    def load_profile_data(self):
        """Load existing profile data into the form."""
        if not self.profile:
            return
            
        try:
            # 기본 정보
            self.name_edit.setText(self.profile.name)
            self.description_edit.setPlainText(self.profile.description)
            
            # 프로필 타입 변환
            type_mapping = {
                "window_config": 0,
                "layout": 1, 
                "application": 2,
                "workspace": 3
            }
            if hasattr(self.profile.profile_type, 'value'):
                type_val = self.profile.profile_type.value
            else:
                type_val = str(self.profile.profile_type)
            
            self.profile_type_combo.setCurrentIndex(type_mapping.get(type_val, 0))
            
            # 기존 auto_apply 설정을 auto_apply_check로 매핑
            self.auto_apply_check.setChecked(getattr(self.profile, 'auto_apply', False))
            self.enabled_check.setChecked(self.profile.enabled)
            
            # 매칭 설정
            if self.profile.matching_criteria:
                criteria = self.profile.matching_criteria
                
                # 전략 매핑
                strategy_mapping = {
                    "title_contains": 0,
                    "exact_title": 1,
                    "title_regex": 2,
                    "process_name": 3,
                    "executable_path": 4,
                    "combined": 5
                }
                
                if hasattr(criteria.strategy, 'value'):
                    strategy_val = criteria.strategy.value
                else:
                    strategy_val = str(criteria.strategy)
                    
                self.matching_strategy_combo.setCurrentIndex(strategy_mapping.get(strategy_val, 0))
                
                if criteria.window_title_pattern:
                    self.window_title_edit.setText(criteria.window_title_pattern)
                if criteria.process_name_pattern:
                    self.process_name_edit.setText(criteria.process_name_pattern)
                if criteria.executable_path_pattern:
                    self.executable_path_edit.setText(criteria.executable_path_pattern)
                    
                self.case_sensitive_check.setChecked(criteria.case_sensitive)
                self.priority_spin.setValue(criteria.priority)
            
            # 창 설정
            if self.profile.window_config:
                config = self.profile.window_config
                self.x_spin.setValue(config.x)
                self.y_spin.setValue(config.y)
                self.width_spin.setValue(config.width)
                self.height_spin.setValue(config.height)
                
                self.maximized_check.setChecked(config.is_maximized)
                self.minimized_check.setChecked(config.is_minimized)
                self.always_on_top_check.setChecked(config.always_on_top)
                
                self.opacity_spin.setValue(int(config.opacity * 100))
                self.monitor_index_spin.setValue(config.monitor_index)
            
            # Load hotkey settings
            if hasattr(self.profile, 'hotkey_enabled'):
                self.hotkey_enabled_check.setChecked(self.profile.hotkey_enabled)
            # 레거시 단축키 설정은 첫 번째 세트로 로드
            if hasattr(self.profile, 'hotkey_combination') and self.profile.hotkey_combination:
                if len(self.hotkey_sets) > 0:
                    self.hotkey_sets[0]['keys'].set_hotkey_string(self.profile.hotkey_combination)
                    self.hotkey_sets[0]['enabled'].setChecked(True)
            
            # Load hotkey sets
            if hasattr(self.profile, 'hotkey_sets') and self.profile.hotkey_sets:
                for i, hotkey_set in enumerate(self.profile.hotkey_sets[:3]):  # 최대 3개
                    if i < len(self.hotkey_sets):
                        self.hotkey_sets[i]['enabled'].setChecked(hotkey_set.get('enabled', False))
                        self.hotkey_sets[i]['keys'].set_hotkey_string(hotkey_set.get('combination', ''))
                        
                        # 액션 설정
                        action_mapping = {
                            'apply_profile': 0,
                            'release_profile': 1,
                            'always_on_top_toggle': 2,
                            'auto_apply_toggle': 3
                        }
                        action_idx = action_mapping.get(hotkey_set.get('action', 'apply_profile'), 0)
                        self.hotkey_sets[i]['action'].setCurrentIndex(action_idx)
            
            # Load advanced features
            if hasattr(self.profile, 'lock_position'):
                self.lock_position_check.setChecked(self.profile.lock_position)
            if hasattr(self.profile, 'mouse_constraint'):
                self.mouse_constraint_check.setChecked(self.profile.mouse_constraint)
            if hasattr(self.profile, 'constraint_escape_key'):
                self.constraint_escape_widget.set_hotkey_string(self.profile.constraint_escape_key)
            
            
        except Exception as e:
            logger.error(f"Error loading profile data: {e}")
    
    def save_profile(self):
        """Save the profile data."""
        try:
            # 유효성 검사
            if not self.name_edit.text().strip():
                show_themed_warning(self, "유효성 검사", "프로필명을 입력해주세요.")
                return
            
            strategy = self.matching_strategy_combo.currentData()
            title_pattern = self.window_title_edit.text().strip()
            process_pattern = self.process_name_edit.text().strip()
            executable_path = self.executable_path_edit.text().strip()
            required_values = {
                'title_contains': title_pattern,
                'exact_title': title_pattern,
                'title_regex': title_pattern,
                'process_name': process_pattern,
                'executable_path': executable_path,
                'combined': title_pattern or process_pattern or executable_path
            }
            if not required_values.get(strategy):
                show_themed_warning(
                    self,
                    "유효성 검사",
                    "선택한 매칭 방식에 필요한 값을 입력해주세요."
                )
                return
            
            hotkey_sets = self._collect_hotkey_sets()
            primary_hotkey = hotkey_sets[0] if hotkey_sets else {}

            # 프로필 데이터 수집
            profile_data = {
                'name': self.name_edit.text().strip(),
                'description': self.description_edit.toPlainText().strip(),
                'auto_apply': self.auto_apply_check.isChecked(),
                'enabled': self.enabled_check.isChecked(),
                'window_config': {
                    'x': self.x_spin.value(),
                    'y': self.y_spin.value(), 
                    'width': self.width_spin.value(),
                    'height': self.height_spin.value(),
                    'is_maximized': self.maximized_check.isChecked(),
                    'is_minimized': self.minimized_check.isChecked(),
                    'always_on_top': self.always_on_top_check.isChecked(),
                    'opacity': self.opacity_spin.value() / 100.0,
                    'monitor_index': self.monitor_index_spin.value()
                },
                'matching_criteria': {
                    'strategy': strategy,
                    'window_title_pattern': title_pattern,
                    'process_name_pattern': process_pattern,
                    'executable_path_pattern': executable_path,
                    'case_sensitive': self.case_sensitive_check.isChecked(),
                    'priority': self.priority_spin.value()
                },
                # Hotkey fields (individual fields for Profile class compatibility)
                'hotkey_enabled': self.hotkey_enabled_check.isChecked(),
                'hotkey_combination': primary_hotkey.get('combination', ''),
                'hotkey_action': primary_hotkey.get('action', 'apply_profile'),
                'hotkey_sets': hotkey_sets,
                # Advanced feature fields (individual fields for Profile class compatibility)
                'lock_position': self.lock_position_check.isChecked(),
                'mouse_constraint': self.mouse_constraint_check.isChecked(),
                'constraint_mode': 'strict',  # Default mode
                'constraint_escape_key': self.constraint_escape_widget.get_hotkey_string(),
                'auto_restore': {
                    'enabled': self.auto_apply_check.isChecked(),
                    'method': 'hybrid',
                    'polling_interval': 2.0,
                    'quick_response': True,
                    'tolerance': 5,
                    'restore_on_focus': True,
                    'restore_on_resize': True,
                    'restore_on_move': True,
                    'pause_when_inactive': False,
                    'max_attempts': -1  # 무제한
                }
            }
            
            if self.save_handler is not None:
                if not self.save_handler(profile_data):
                    return
            else:
                self.profile_saved.emit(profile_data)
            
            # 저장 후 자동 적용
            apply_result = self._apply_saved_profile(profile_data)
            
            # 적용 결과에 따른 상세 메시지 생성
            if 'error' in apply_result:
                message = f"프로필이 저장되었지만 적용 중 오류가 발생했습니다:\n{apply_result['error']}"
                show_themed_warning(self, "저장 완료 (적용 오류)", message)
            elif apply_result['applied_count'] > 0:
                windows_list = '\n'.join(apply_result['matched_windows'][:3])  # 최대 3개만 표시
                if len(apply_result['matched_windows']) > 3:
                    windows_list += f"\n... 외 {len(apply_result['matched_windows']) - 3}개"
                message = f"프로필이 성공적으로 저장되고 {apply_result['applied_count']}개 창에 적용되었습니다.\n\n적용된 창:\n{windows_list}"
                show_themed_information(self, "저장 및 적용 완료", message)
            elif apply_result['matched_count'] > 0:
                message = f"프로필이 저장되었습니다.\n\n{apply_result['matched_count']}개의 일치하는 창을 찾았지만 적용에 실패했습니다.\n창이 최소화되어 있거나 다른 프로그램에 의해 제어되고 있을 수 있습니다."
                show_themed_warning(self, "저장 완료 (적용 실패)", message)
            else:
                message = f"프로필이 저장되었습니다.\n\n현재 조건에 맞는 창이 실행되지 않아 즉시 적용되지 않았습니다.\n\n설정된 조건:\n창 제목: '{profile_data['matching_criteria']['window_title_pattern']}'\n프로세스: '{profile_data['matching_criteria']['process_name_pattern']}'\n실행 파일: '{profile_data['matching_criteria']['executable_path_pattern']}'"
                show_themed_information(self, "저장 완료", message)
            
            self.accept()
            
        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            show_themed_critical(self, "저장 오류", f"프로필 저장 중 오류가 발생했습니다: {str(e)}")
    
    def _collect_hotkey_sets(self) -> List[Dict[str, Any]]:
        """Collect hotkey sets data for saving."""
        hotkey_sets = []
        
        action_mapping = [
            'apply_profile',
            'release_profile', 
            'always_on_top_toggle',
            'auto_apply_toggle'
        ]
        
        for hotkey_set in self.hotkey_sets:
            if hotkey_set['enabled'].isChecked():
                combination = hotkey_set['keys'].get_hotkey_string()
                if combination and combination.strip():
                    action_idx = hotkey_set['action'].currentIndex()
                    action = action_mapping[action_idx] if 0 <= action_idx < len(action_mapping) else 'apply_profile'
                    
                    hotkey_sets.append({
                        'enabled': True,
                        'combination': combination,
                        'action': action
                    })
        
        return hotkey_sets
    
    def _apply_saved_profile(self, profile_data: Dict[str, Any]):
        """Apply the saved profile to matching windows immediately."""
        try:
            from core.window_enumerator import WindowEnumerator
            from core.profile_manager import ProfileManager, Profile
            
            # Create temporary profile from data - filter out unknown fields
            # Remove fields that Profile class doesn't recognize
            filtered_data = {k: v for k, v in profile_data.items() 
                           if k not in ['hotkey_sets']}  # Remove unknown fields
            temp_profile = Profile.from_dict(filtered_data)
            
            # Get current windows
            enumerator = WindowEnumerator()
            windows_info = enumerator.enumerate_windows()
            
            # Find matching windows and apply profile
            applied_count = 0
            matched_windows = []
            
            for enhanced_window in windows_info:
                # Convert EnhancedWindowInfo to dictionary format expected by Profile methods
                window_dict = {
                    'hwnd': enhanced_window.hwnd,
                    'title': enhanced_window.title,
                    'class_name': enhanced_window.class_name,
                    'rect': (enhanced_window.rect.left, enhanced_window.rect.top, 
                           enhanced_window.rect.right, enhanced_window.rect.bottom) if enhanced_window.rect else (0,0,0,0),
                    'is_visible': enhanced_window.is_visible,
                    'is_minimized': enhanced_window.is_minimized,
                    'is_maximized': enhanced_window.is_maximized,
                    'process_name': enhanced_window.process_info.name if enhanced_window.process_info else '',
                    'process_id': enhanced_window.process_info.pid if enhanced_window.process_info else 0,
                    'executable_path': enhanced_window.process_info.exe_path if enhanced_window.process_info else ''
                }
                
                if temp_profile.matches_window(window_dict):
                    window_title = enhanced_window.title or 'Unknown'
                    matched_windows.append(window_title)
                    success = temp_profile.apply_to_window(window_dict)
                    if success:
                        applied_count += 1
                        logger.info(f"Applied profile to window: {window_title}")
            
            # Return detailed result for user feedback
            return {
                'matched_count': len(matched_windows),
                'applied_count': applied_count,
                'matched_windows': matched_windows
            }
                
        except Exception as e:
            logger.error(f"Error applying saved profile: {e}")
            return {
                'matched_count': 0,
                'applied_count': 0,
                'matched_windows': [],
                'error': str(e)
            }
    
    def find_target_window(self):
        """Find the target window based on profile criteria."""
        try:
            import win32gui
            import win32process
            import psutil
            import re
            
            window_title_pattern = self.window_title_edit.text().strip()
            process_name_pattern = self.process_name_edit.text().strip()
            
            if not window_title_pattern and not process_name_pattern:
                return None, "창 제목 또는 프로세스 이름이 설정되지 않았습니다."
            
            found_windows = []
            
            def enum_windows_proc(hwnd, lParam):
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                    
                try:
                    window_title = win32gui.GetWindowText(hwnd)
                    if not window_title:
                        return True
                    
                    # Get process name
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        process = psutil.Process(pid)
                        process_name = process.name()
                    except:
                        return True
                    
                    # Check title match
                    title_match = False
                    if window_title_pattern:
                        if window_title_pattern.lower() in window_title.lower():
                            title_match = True
                    
                    # Check process match
                    process_match = False
                    if process_name_pattern:
                        if process_name_pattern.lower() in process_name.lower():
                            process_match = True
                    
                    # If both patterns are specified, both must match
                    if window_title_pattern and process_name_pattern:
                        if title_match and process_match:
                            found_windows.append((hwnd, window_title, process_name))
                    # If only one pattern is specified, that one must match
                    elif window_title_pattern and title_match:
                        found_windows.append((hwnd, window_title, process_name))
                    elif process_name_pattern and process_match:
                        found_windows.append((hwnd, window_title, process_name))
                    
                except Exception as e:
                    pass  # Skip windows that cause errors
                
                return True
            
            win32gui.EnumWindows(enum_windows_proc, 0)
            
            if not found_windows:
                return None, f"조건에 맞는 창을 찾을 수 없습니다.\n창 제목: '{window_title_pattern}'\n프로세스: '{process_name_pattern}'"
            
            if len(found_windows) > 1:
                # If multiple windows found, prefer the first one but inform user
                hwnd, title, process = found_windows[0]
                return hwnd, f"여러 창이 발견되어 첫 번째 창을 선택했습니다.\n창: {title}\n프로세스: {process}"
            
            hwnd, title, process = found_windows[0]
            return hwnd, f"창을 찾았습니다.\n창: {title}\n프로세스: {process}"
            
        except ImportError:
            return None, "Windows API를 사용할 수 없습니다."
        except Exception as e:
            logger.error(f"Error finding target window: {e}")
            return None, f"창을 찾는 중 오류가 발생했습니다: {str(e)}"

    def get_current_window_position(self):
        """Get the position of the target window based on profile criteria."""
        try:
            import win32gui
            
            # Find target window based on profile criteria
            hwnd, message = self.find_target_window()
            
            if not hwnd:
                show_themed_warning(self, "창 위치 가져오기", message)
                return
            
            # Get window rectangle
            try:
                rect = win32gui.GetWindowRect(hwnd)
                x = rect[0]
                y = rect[1]
                
                # Update the position fields
                self.x_spin.setValue(x)
                self.y_spin.setValue(y)
                
                show_themed_information(
                    self, 
                    "위치 가져오기 완료", 
                    f"{message}\n\n위치: X={x}, Y={y}"
                )
                
                logger.info(f"Retrieved window position: X={x}, Y={y}")
                
            except Exception as e:
                logger.error(f"Error getting window rect: {e}")
                show_themed_warning(self, "오류", f"창 위치를 가져오는 중 오류가 발생했습니다: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in get_current_window_position: {e}")
            show_themed_warning(self, "오류", f"창 위치를 가져오는 중 오류가 발생했습니다: {str(e)}")
    
    def get_current_window_size(self):
        """Get the size of the target window based on profile criteria."""
        try:
            import win32gui
            
            # Find target window based on profile criteria
            hwnd, message = self.find_target_window()
            
            if not hwnd:
                show_themed_warning(self, "창 크기 가져오기", message)
                return
            
            # Get window rectangle
            try:
                rect = win32gui.GetWindowRect(hwnd)
                width = rect[2] - rect[0]  # right - left
                height = rect[3] - rect[1]  # bottom - top
                
                # Update the size fields
                self.width_spin.setValue(width)
                self.height_spin.setValue(height)
                
                show_themed_information(
                    self, 
                    "크기 가져오기 완료", 
                    f"{message}\n\n크기: 폭={width}px, 높이={height}px"
                )
                
                logger.info(f"Retrieved window size: {width}x{height}")
                
            except Exception as e:
                logger.error(f"Error getting window rect: {e}")
                show_themed_warning(self, "오류", f"창 크기를 가져오는 중 오류가 발생했습니다: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in get_current_window_size: {e}")
            show_themed_warning(self, "오류", f"창 크기를 가져오는 중 오류가 발생했습니다: {str(e)}")
    
    def set_resolution(self, width: int, height: int):
        """Set resolution preset."""
        self.width_spin.setValue(width)
        self.height_spin.setValue(height)
        logger.info(f"Set resolution to {width}x{height}")
    
    def center_window(self):
        """Center window on screen."""
        try:
            import win32api
            
            # Get primary monitor resolution
            screen_width = win32api.GetSystemMetrics(0)  # SM_CXSCREEN
            screen_height = win32api.GetSystemMetrics(1)  # SM_CYSCREEN
            
            # Calculate center position
            window_width = self.width_spin.value() if self.width_spin.value() > 0 else 800
            window_height = self.height_spin.value() if self.height_spin.value() > 0 else 600
            
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            self.x_spin.setValue(x)
            self.y_spin.setValue(y)
            
            logger.info(f"Centered window at {x}, {y} on {screen_width}x{screen_height} screen")
            
        except Exception as e:
            logger.error(f"Error centering window: {e}")
            # Fallback to common resolution center
            self.x_spin.setValue(560)  # (1920-800)/2
            self.y_spin.setValue(540)  # (1080-600)/2
    
    def set_position_preset(self, position: str):
        """Set position preset."""
        try:
            import win32api
            
            # Get primary monitor resolution
            screen_width = win32api.GetSystemMetrics(0)
            screen_height = win32api.GetSystemMetrics(1)
            
            window_width = self.width_spin.value() if self.width_spin.value() > 0 else 800
            window_height = self.height_spin.value() if self.height_spin.value() > 0 else 600
            
            if position == "top":
                x = (screen_width - window_width) // 2
                y = 0
            elif position == "bottom":
                x = (screen_width - window_width) // 2
                y = screen_height - window_height
            elif position == "left":
                x = 0
                y = (screen_height - window_height) // 2
            elif position == "right":
                x = screen_width - window_width
                y = (screen_height - window_height) // 2
            else:
                return
            
            self.x_spin.setValue(x)
            self.y_spin.setValue(y)
            
            logger.info(f"Set {position} position: {x}, {y}")
            
        except Exception as e:
            logger.error(f"Error setting {position} position: {e}")
    
    def apply_theme_styling(self, _theme_name=None):
        """Apply current theme styling to all UI elements."""
        try:
            if not hasattr(self, 'theme_manager') or not self.theme_manager:
                return
                
            current_theme = self.theme_manager.current_theme

            if self.theme_manager.current_scheme:
                bg = self.theme_manager.get_color_string(ThemeElement.BACKGROUND)
                fg = self.theme_manager.get_color_string(ThemeElement.FOREGROUND)
                button = self.theme_manager.get_color_string(ThemeElement.BUTTON)
                button_hover = self.theme_manager.get_color_string(ThemeElement.BUTTON_HOVER)
                button_pressed = self.theme_manager.get_color_string(ThemeElement.BUTTON_PRESSED)
                text = self.theme_manager.get_color_string(ThemeElement.TEXT)
                accent = self.theme_manager.get_color_string(ThemeElement.ACCENT)
                border = self.theme_manager.get_color_string(ThemeElement.BORDER)
                disabled = self.theme_manager.get_color_string(ThemeElement.DISABLED)

                self.setStyleSheet(f"""
                    QDialog {{ background-color: {bg}; color: {text}; }}
                    QGroupBox {{
                        background-color: {fg}; border: 1px solid {border};
                        border-radius: 5px; margin-top: 10px; padding-top: 5px;
                        color: {text}; font-weight: bold;
                    }}
                    QGroupBox::title {{
                        subcontrol-origin: margin; subcontrol-position: top left;
                        padding: 0 5px; color: {text};
                    }}
                    QLabel, QCheckBox, QRadioButton {{ color: {text}; background-color: transparent; }}
                    QLineEdit, QSpinBox, QComboBox, QTextEdit {{
                        background-color: {fg}; border: 1px solid {border}; border-radius: 3px;
                        padding: 5px; color: {text};
                    }}
                    QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
                        border: 2px solid {accent};
                    }}
                    QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {{
                        background-color: {button}; border: none;
                    }}
                    QComboBox QAbstractItemView {{
                        background-color: {fg}; color: {text}; border: 1px solid {border};
                        selection-background-color: {accent}; selection-color: {bg};
                    }}
                    QCheckBox::indicator, QRadioButton::indicator {{
                        background-color: {fg}; border: 1px solid {border};
                    }}
                    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
                        background-color: {accent};
                    }}
                    QPushButton {{
                        background-color: {button}; color: {text}; border: 1px solid {border};
                        border-radius: 3px; padding: 4px 8px; font-weight: bold;
                    }}
                    QPushButton:hover {{ background-color: {button_hover}; }}
                    QPushButton:pressed {{ background-color: {button_pressed}; }}
                    QPushButton:disabled {{ background-color: {fg}; color: {disabled}; }}
                    QTabWidget::pane {{ background-color: {fg}; border: 1px solid {border}; }}
                    QTabBar::tab {{
                        background-color: {button}; color: {text}; border: 1px solid {border};
                        padding: 5px 8px; margin-right: 2px;
                    }}
                    QTabBar::tab:selected {{ background-color: {accent}; color: {bg}; }}
                    QTabBar::tab:hover {{ background-color: {button_hover}; }}
                """)
                self.ui_scale_manager.refresh_stylesheet(self)
                return
            
            # Convert to string if it's an enum
            if hasattr(current_theme, 'value'):
                theme_str = current_theme.value
            else:
                theme_str = str(current_theme)
            
            if theme_str == "dark":
                # Dark theme styling for profile editor
                self.setStyleSheet("""
                    QDialog {
                        background-color: #2b2b2b;
                        color: #ffffff;
                    }
                    QGroupBox {
                        background-color: #3c3c3c;
                        border: 1px solid #555555;
                        border-radius: 5px;
                        margin-top: 10px;
                        padding-top: 5px;
                        color: #ffffff;
                        font-weight: bold;
                    }
                    QGroupBox::title {
                        subcontrol-origin: margin;
                        subcontrol-position: top left;
                        padding: 0 5px;
                        color: #ffffff;
                    }
                    QLabel {
                        color: #ffffff;
                        background-color: transparent;
                    }
                    QLineEdit {
                        background-color: #4a4a4a;
                        border: 1px solid #666666;
                        border-radius: 3px;
                        padding: 5px;
                        color: #ffffff;
                    }
                    QLineEdit:focus {
                        border: 2px solid #0078d4;
                    }
                    QSpinBox {
                        background-color: #4a4a4a;
                        border: 1px solid #666666;
                        border-radius: 3px;
                        padding: 5px;
                        color: #ffffff;
                    }
                    QSpinBox::up-button, QSpinBox::down-button {
                        background-color: #4a4a4a;
                        color: #ffffff;
                        border: 1px solid #666666;
                    }
                    QComboBox {
                        background-color: #4a4a4a;
                        border: 1px solid #666666;
                        border-radius: 3px;
                        padding: 5px;
                        color: #ffffff;
                    }
                    QComboBox::drop-down {
                        background-color: #4a4a4a;
                        border: none;
                    }
                    QComboBox::down-arrow {
                        color: #ffffff;
                    }
                    QComboBox QAbstractItemView {
                        background-color: #4a4a4a;
                        color: #ffffff;
                        selection-background-color: #0078d4;
                    }
                    QCheckBox {
                        color: #ffffff;
                        background-color: transparent;
                    }
                    QCheckBox::indicator {
                        background-color: #4a4a4a;
                        border: 1px solid #666666;
                    }
                    QCheckBox::indicator:checked {
                        background-color: #0078d4;
                    }
                    QRadioButton {
                        color: #ffffff;
                        background-color: transparent;
                    }
                    QRadioButton::indicator {
                        background-color: #4a4a4a;
                        border: 1px solid #666666;
                        border-radius: 6px;
                    }
                    QRadioButton::indicator:checked {
                        background-color: #0078d4;
                    }
                    QTextEdit {
                        background-color: #4a4a4a;
                        border: 1px solid #666666;
                        border-radius: 3px;
                        color: #ffffff;
                        padding: 5px;
                    }
                    QPushButton {
                        background-color: #0078d4;
                        color: #ffffff;
                        border: none;
                        border-radius: 3px;
                        padding: 8px 15px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #106ebe;
                    }
                    QPushButton:pressed {
                        background-color: #005a9e;
                    }
                    QPushButton:disabled {
                        background-color: #555555;
                        color: #888888;
                    }
                    QTabWidget::pane {
                        background-color: #3c3c3c;
                        border: 1px solid #555555;
                    }
                    QTabBar::tab {
                        background-color: #4a4a4a;
                        color: #ffffff;
                        border: 1px solid #666666;
                        padding: 8px 15px;
                        margin-right: 2px;
                    }
                    QTabBar::tab:selected {
                        background-color: #0078d4;
                    }
                    QTabBar::tab:hover {
                        background-color: #555555;
                    }
                """)
            else:
                # Light theme - remove custom styling to use default
                self.setStyleSheet("")

            self.ui_scale_manager.refresh_stylesheet(self)
                
        except Exception as e:
            logger.error(f"Error applying theme to profile editor: {e}")

    def apply_ui_scale(self, _scale_percent):
        """Reapply the dialog stylesheet from unscaled theme values."""
        self.apply_theme_styling()
        self.window_settings_content.setMinimumHeight(
            self.window_settings_content.sizeHint().height()
        )
    
