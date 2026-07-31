"""
Debug Window
============

실시간 디버그 메시지 출력 창
"""

import os
import logging
import datetime
from typing import Optional
from io import StringIO

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
    QCheckBox, QComboBox, QLabel, QFileDialog, QMessageBox,
    QGroupBox, QSpinBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor


class LogHandler(logging.Handler):
    """로그를 실시간으로 캡처하는 핸들러"""
    
    def __init__(self, debug_window):
        super().__init__()
        self.debug_window = debug_window
        
    def emit(self, record):
        """로그 레코드를 디버그 창으로 전송"""
        try:
            msg = self.format(record)
            self.debug_window.add_log_message(msg, record.levelname)
        except Exception:
            pass  # 디버그 창에서 오류가 발생해도 무시


class DebugWindow(QDialog):
    """실시간 디버그 메시지 출력 창"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_messages = []
        self.max_messages = 1000
        self.log_handler = None
        self.auto_scroll = True
        
        self.setWindowTitle("실시간 디버그 창")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        # 창을 부모 창과 독립적으로 만듦
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_DeleteOnClose, False)  # 창 닫아도 삭제하지 않음
        
        self.setup_ui()
        self.setup_logging()
        
    def setup_ui(self):
        """UI 설정"""
        layout = QVBoxLayout(self)
        
        # 컨트롤 패널
        control_group = QGroupBox("디버그 설정")
        control_layout = QHBoxLayout(control_group)
        
        # 로그 레벨 선택
        control_layout.addWidget(QLabel("로그 레벨:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level_combo.setCurrentText("INFO")
        self.log_level_combo.currentTextChanged.connect(self.change_log_level)
        control_layout.addWidget(self.log_level_combo)
        
        # 자동 스크롤
        self.auto_scroll_check = QCheckBox("자동 스크롤")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.toggled.connect(self.toggle_auto_scroll)
        control_layout.addWidget(self.auto_scroll_check)
        
        # 최대 메시지 수
        control_layout.addWidget(QLabel("최대 메시지:"))
        self.max_messages_spin = QSpinBox()
        self.max_messages_spin.setMinimum(100)
        self.max_messages_spin.setMaximum(10000)
        self.max_messages_spin.setValue(1000)
        self.max_messages_spin.valueChanged.connect(self.change_max_messages)
        control_layout.addWidget(self.max_messages_spin)
        
        control_layout.addStretch()
        
        # 메시지 카운터
        self.message_count_label = QLabel("메시지: 0")
        control_layout.addWidget(self.message_count_label)
        
        layout.addWidget(control_group)
        
        # 로그 출력 영역
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 9))
        
        # 다크 테마 스타일
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
        """)
        
        layout.addWidget(self.log_display)
        
        # 하단 버튼
        button_layout = QHBoxLayout()
        
        self.clear_button = QPushButton("로그 지우기")
        self.clear_button.clicked.connect(self.clear_logs)
        button_layout.addWidget(self.clear_button)
        
        self.copy_button = QPushButton("전체 복사")
        self.copy_button.clicked.connect(self.copy_all_logs)
        button_layout.addWidget(self.copy_button)
        
        self.export_button = QPushButton("파일로 내보내기")
        self.export_button.clicked.connect(self.export_to_file)
        button_layout.addWidget(self.export_button)
        
        button_layout.addStretch()
        
        self.close_button = QPushButton("창 숨기기")
        self.close_button.clicked.connect(self.hide)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        
        # 타이머 설정 (UI 업데이트용)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(500)  # 0.5초마다 업데이트
        
    def setup_logging(self):
        """로깅 설정"""
        # 기존 루트 로거에 핸들러 추가
        root_logger = logging.getLogger()
        
        # 이미 추가된 핸들러가 있으면 제거
        if self.log_handler:
            root_logger.removeHandler(self.log_handler)
        
        # 새 핸들러 추가
        self.log_handler = LogHandler(self)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        self.log_handler.setFormatter(formatter)
        
        # 로그 레벨 설정
        level = getattr(logging, self.log_level_combo.currentText())
        self.log_handler.setLevel(level)
        
        root_logger.addHandler(self.log_handler)
        
    def change_log_level(self, level_name):
        """로그 레벨 변경"""
        if self.log_handler:
            level = getattr(logging, level_name)
            self.log_handler.setLevel(level)
            
    def toggle_auto_scroll(self, enabled):
        """자동 스크롤 토글"""
        self.auto_scroll = enabled
        
    def change_max_messages(self, max_messages):
        """최대 메시지 수 변경"""
        self.max_messages = max_messages
        
        # 현재 메시지가 최대치를 초과하면 잘라냄
        if len(self.log_messages) > self.max_messages:
            self.log_messages = self.log_messages[-self.max_messages:]
            
    def add_log_message(self, message, level):
        """로그 메시지 추가"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {level}: {message}"
        
        self.log_messages.append(formatted_message)
        
        # 최대 메시지 수 제한
        if len(self.log_messages) > self.max_messages:
            self.log_messages = self.log_messages[-self.max_messages:]
            
    def update_display(self):
        """디스플레이 업데이트"""
        if not self.log_messages:
            return
            
        # 메시지 카운터 업데이트
        self.message_count_label.setText(f"메시지: {len(self.log_messages)}")
        
        # 새 메시지가 있으면 디스플레이 업데이트
        current_text = self.log_display.toPlainText()
        new_text = "\n".join(self.log_messages)
        
        if current_text != new_text:
            # 현재 스크롤 위치 저장
            scrollbar = self.log_display.verticalScrollBar()
            at_bottom = scrollbar.value() >= scrollbar.maximum() - 10
            
            self.log_display.setPlainText(new_text)
            
            # 자동 스크롤이 활성화되어 있거나 이미 맨 아래에 있었으면 스크롤
            if self.auto_scroll or at_bottom:
                self.log_display.moveCursor(QTextCursor.End)
                
    def clear_logs(self):
        """로그 지우기"""
        self.log_messages.clear()
        self.log_display.clear()
        self.message_count_label.setText("메시지: 0")
        
    def copy_all_logs(self):
        """전체 로그 복사"""
        if self.log_messages:
            from PyQt5.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(self.log_messages))
            QMessageBox.information(self, "복사 완료", "모든 로그가 클립보드에 복사되었습니다.")
        else:
            QMessageBox.information(self, "알림", "복사할 로그가 없습니다.")
            
    def export_to_file(self):
        """파일로 내보내기"""
        if not self.log_messages:
            QMessageBox.information(self, "알림", "내보낼 로그가 없습니다.")
            return
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"debug_log_{timestamp}.txt"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "디버그 로그 저장",
            default_filename,
            "텍스트 파일 (*.txt);;모든 파일 (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"WindowResizer 디버그 로그\n")
                    f.write(f"생성 시간: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("="*50 + "\n\n")
                    
                    for message in self.log_messages:
                        f.write(message + "\n")
                        
                QMessageBox.information(self, "내보내기 완료", f"로그가 파일로 저장되었습니다:\n{file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "오류", f"파일 저장 중 오류가 발생했습니다:\n{str(e)}")
                
    def closeEvent(self, event):
        """창 닫기 이벤트 - 실제로는 숨기기만 함"""
        self.hide()
        event.ignore()
        
    def cleanup(self):
        """리소스 정리"""
        if self.log_handler:
            root_logger = logging.getLogger()
            root_logger.removeHandler(self.log_handler)
            self.log_handler = None
            
        if self.update_timer:
            self.update_timer.stop()