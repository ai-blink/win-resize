"""
향상된 창 모니터링 시스템
========================

이벤트 기반 + 스마트 폴링 조합으로 효율적인 창 상태 모니터링
창 변화 감지 시점에만 복구하여 시스템 리소스 최적화
"""

import ctypes
from ctypes import wintypes
import win32gui
import win32con
import win32api
import logging
import threading
import time
import os
from typing import Dict, Optional, Callable, Set
from dataclasses import dataclass
from enum import Enum
import json

logger = logging.getLogger(__name__)

class MonitoringMethod(Enum):
    """모니터링 방식"""
    EVENT_ONLY = "event_only"          # 이벤트만 사용
    POLLING_ONLY = "polling_only"      # 폴링만 사용  
    HYBRID = "hybrid"                  # 이벤트 + 폴링 조합

class WindowState(Enum):
    """창 상태"""
    NORMAL = "normal"
    MINIMIZED = "minimized"
    MAXIMIZED = "maximized"
    DESTROYED = "destroyed"

@dataclass
class WindowMonitorConfig:
    """창 모니터링 설정"""
    hwnd: int
    window_title: str
    target_rect: tuple  # (left, top, right, bottom)
    
    # 모니터링 설정
    method: MonitoringMethod = MonitoringMethod.HYBRID
    polling_interval: float = 2.0      # 기본 폴링 간격 (초)
    quick_response_interval: float = 0.3   # 변화 감지 시 빠른 응답 간격
    pause_when_inactive: bool = True   # 비활성화 시 모니터링 일시정지
    
    # 복구 설정
    auto_restore: bool = True
    restore_on_focus: bool = True      # 포커스 복귀 시 복구
    restore_on_resize: bool = True     # 크기 변경 시 복구
    restore_on_move: bool = True       # 위치 변경 시 복구
    
    # 성능 설정
    tolerance: int = 5                 # 허용 오차 (픽셀)
    max_restore_attempts: int = 50
    adaptive_polling: bool = True      # 적응형 폴링 간격
    
    # 런타임 상태
    created_time: float = 0.0
    restore_attempts: int = 0
    last_change_time: float = 0.0
    is_game_window: bool = False

class EnhancedWindowMonitor:
    """향상된 창 모니터링 시스템"""
    
    def __init__(self):
        self.monitored_windows: Dict[int, WindowMonitorConfig] = {}
        self.event_hook = None
        self.polling_thread = None
        self.polling_active = False
        self._stop_polling = threading.Event()
        
        # 성능 통계
        self.stats = {
            'events_received': 0,
            'polling_checks': 0,
            'restorations_performed': 0,
            'false_positives': 0,  # 변화가 없었던 체크
            'quick_responses': 0   # 빠른 응답 모드 진입 횟수
        }
        
        # 상태 관리
        self.window_states: Dict[int, WindowState] = {}
        self.last_foreground_window = None
        self.quick_response_mode = False
        self.quick_response_end_time = 0
        
        logger.info("향상된 창 모니터링 시스템 초기화 완료")
    
    def _setup_event_hook(self):
        """Windows 이벤트 후킹 설정 (ctypes 사용)"""
        try:
            # WinEventHook 프로시저 정의
            def win_event_proc(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
                try:
                    if hwnd in self.monitored_windows:
                        self.stats['events_received'] += 1
                        
                        # 이벤트 타입별 처리
                        if event == win32con.EVENT_OBJECT_LOCATIONCHANGE:
                            logger.debug(f"위치/크기 변경 이벤트: {hwnd}")
                            self._handle_window_change(hwnd, "location_change")
                            
                        elif event == win32con.EVENT_SYSTEM_FOREGROUND:
                            logger.debug(f"포커스 변경 이벤트: {hwnd}")
                            self._handle_window_change(hwnd, "focus_change")
                            
                        elif event == win32con.EVENT_OBJECT_STATECHANGE:
                            logger.debug(f"상태 변경 이벤트: {hwnd}")
                            self._handle_window_change(hwnd, "state_change")
                            
                except Exception as e:
                    logger.error(f"이벤트 처리 오류: {e}")
                return 0
            
            # ctypes로 SetWinEventHook 직접 호출
            try:
                # WinEventProc 타입 정의
                from ctypes.wintypes import HANDLE, DWORD, LONG
                
                WINEVENTPROC = ctypes.WINFUNCTYPE(None, HANDLE, DWORD, HANDLE, LONG, LONG, DWORD, DWORD)
                
                # 프로시저 래퍼
                self.event_proc = WINEVENTPROC(win_event_proc)
                
                # SetWinEventHook 호출 (Unicode 버전 사용)
                self.event_hook = ctypes.windll.user32.SetWinEventHookW(
                    win32con.EVENT_OBJECT_LOCATIONCHANGE,  # 최소 이벤트
                    win32con.EVENT_SYSTEM_FOREGROUND,      # 최대 이벤트  
                    None,  # 모든 모듈
                    self.event_proc,
                    0,  # 모든 프로세스
                    0,  # 모든 스레드
                    win32con.WINEVENT_OUTOFCONTEXT
                )
                
                if self.event_hook:
                    logger.info("Windows 이벤트 후킹 설정 성공 (ctypes)")
                    return True
                else:
                    logger.warning("Windows 이벤트 후킹 설정 실패 (ctypes)")
                    return False
                    
            except Exception as ctypes_error:
                logger.warning(f"ctypes를 통한 이벤트 후킹 실패: {ctypes_error}")
                logger.info("폴링 모니터링으로 대체")
                return False
                
        except Exception as e:
            logger.warning(f"이벤트 후킹 설정 오류: {e}")
            logger.info("폴링 모니터링으로 대체")
            return False
    
    def _handle_window_change(self, hwnd: int, event_type: str):
        """창 변경 이벤트 처리"""
        try:
            if hwnd not in self.monitored_windows:
                return
            
            config = self.monitored_windows[hwnd]
            
            # 빠른 응답 모드 활성화
            if config.auto_restore:
                self._activate_quick_response_mode()
                
                # 즉시 상태 확인 및 복구
                threading.Thread(
                    target=self._check_and_restore_window,
                    args=(hwnd, event_type),
                    daemon=True
                ).start()
                
        except Exception as e:
            logger.error(f"창 변경 처리 오류: {e}")
    
    def _activate_quick_response_mode(self):
        """빠른 응답 모드 활성화"""
        self.quick_response_mode = True
        self.quick_response_end_time = time.time() + 5.0  # 5초간 빠른 응답
        self.stats['quick_responses'] += 1
        logger.debug("빠른 응답 모드 활성화 (5초)")
    
    def _start_polling_monitor(self):
        """폴링 모니터링 시작"""
        if self.polling_active:
            return
        
        try:
            self.polling_active = True
            self._stop_polling.clear()
            
            self.polling_thread = threading.Thread(
                target=self._polling_worker,
                name="EnhancedWindowMonitor",
                daemon=True
            )
            self.polling_thread.start()
            
            logger.info("폴링 모니터링 시작")
            
        except Exception as e:
            logger.error(f"폴링 모니터링 시작 오류: {e}")
            self.polling_active = False
    
    def _polling_worker(self):
        """폴링 워커 스레드"""
        logger.info("향상된 폴링 워커 시작")
        
        try:
            while self.polling_active and not self._stop_polling.is_set():
                try:
                    # 적응형 폴링 간격 계산
                    current_interval = self._calculate_polling_interval()
                    
                    # 모니터링 중인 창들 확인
                    for hwnd, config in list(self.monitored_windows.items()):
                        if not win32gui.IsWindow(hwnd):
                            logger.info(f"창이 존재하지 않음, 모니터링 제거: {config.window_title}")
                            self._remove_window(hwnd)
                            continue
                        
                        # 비활성화 시 모니터링 일시정지 옵션 확인 (단, 크기/위치 복구는 항상 수행)
                        if config.pause_when_inactive:
                            current_foreground = win32gui.GetForegroundWindow()
                            if current_foreground != hwnd:
                                # 비활성 창이지만 크기/위치 변경이 감지되면 복구는 수행
                                if self._check_if_window_changed(hwnd, config):
                                    logger.info(f"비활성 창 변경 감지, 복구 수행: {config.window_title}")
                                    self._check_and_restore_window(hwnd, "polling_inactive")
                                continue  # 일반적인 모니터링은 스킵
                        
                        # 창 상태 확인
                        self._check_and_restore_window(hwnd, "polling")
                        self.stats['polling_checks'] += 1
                    
                    # 다음 폴링까지 대기
                    if self._stop_polling.wait(current_interval):
                        break
                        
                except Exception as e:
                    logger.error(f"폴링 워커 오류: {e}")
                    time.sleep(1.0)
            
        except Exception as e:
            logger.error(f"폴링 워커 심각한 오류: {e}")
        finally:
            logger.info(f"향상된 폴링 워커 종료 (체크: {self.stats['polling_checks']}회)")
    
    def _calculate_polling_interval(self) -> float:
        """적응형 폴링 간격 계산"""
        # 빠른 응답 모드 확인
        if self.quick_response_mode:
            if time.time() < self.quick_response_end_time:
                return 0.3  # 빠른 응답 간격
            else:
                self.quick_response_mode = False
                logger.debug("빠른 응답 모드 종료")
        
        # 기본 간격들 계산
        base_intervals = []
        for config in self.monitored_windows.values():
            if config.adaptive_polling:
                # 최근 변화가 있었으면 더 자주 확인
                time_since_change = time.time() - config.last_change_time
                if time_since_change < 30:  # 30초 이내 변화
                    interval = config.polling_interval * 0.5
                elif time_since_change < 300:  # 5분 이내 변화
                    interval = config.polling_interval
                else:  # 오래된 창은 느리게
                    interval = config.polling_interval * 2.0
            else:
                interval = config.polling_interval
            
            base_intervals.append(interval)
        
        if not base_intervals:
            return 2.0
        
        # 가장 빠른 간격 사용 (가장 민감한 설정에 맞춤)
        return min(base_intervals)
    
    def _check_if_window_changed(self, hwnd: int, config: WindowMonitorConfig) -> bool:
        """창이 변경되었는지 빠르게 확인 (복구는 하지 않음)"""
        try:
            if hwnd not in self.monitored_windows:
                return False
            
            # 현재 창 상태 가져오기
            try:
                current_rect = win32gui.GetWindowRect(hwnd)
            except Exception:
                return False
            
            target_rect = config.target_rect
            
            # 위치 변화 확인
            if config.restore_on_move:
                pos_changed = (
                    abs(current_rect[0] - target_rect[0]) > config.tolerance or
                    abs(current_rect[1] - target_rect[1]) > config.tolerance
                )
                if pos_changed:
                    return True
            
            # 크기 변화 확인
            if config.restore_on_resize:
                current_w = current_rect[2] - current_rect[0]
                current_h = current_rect[3] - current_rect[1]
                target_w = target_rect[2] - target_rect[0]
                target_h = target_rect[3] - target_rect[1]
                
                size_changed = (
                    abs(current_w - target_w) > config.tolerance or
                    abs(current_h - target_h) > config.tolerance
                )
                if size_changed:
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"창 변경 확인 오류: {e}")
            return False
    
    def _check_and_restore_window(self, hwnd: int, trigger: str):
        """창 상태 확인 및 필요시 복구"""
        try:
            if hwnd not in self.monitored_windows:
                return
            
            config = self.monitored_windows[hwnd]
            
            # 현재 창 상태 가져오기
            try:
                current_rect = win32gui.GetWindowRect(hwnd)
            except Exception:
                # 창이 사라졌거나 접근 불가
                self._remove_window(hwnd)
                return
            
            target_rect = config.target_rect
            
            # 변화 감지
            needs_restore = False
            changes = []
            
            # 위치 변화 확인
            if config.restore_on_move:
                pos_changed = (
                    abs(current_rect[0] - target_rect[0]) > config.tolerance or
                    abs(current_rect[1] - target_rect[1]) > config.tolerance
                )
                if pos_changed:
                    needs_restore = True
                    changes.append("position")
            
            # 크기 변화 확인
            if config.restore_on_resize:
                current_w = current_rect[2] - current_rect[0]
                current_h = current_rect[3] - current_rect[1]
                target_w = target_rect[2] - target_rect[0]
                target_h = target_rect[3] - target_rect[1]
                
                size_changed = (
                    abs(current_w - target_w) > config.tolerance or
                    abs(current_h - target_h) > config.tolerance
                )
                if size_changed:
                    needs_restore = True
                    changes.append("size")
            
            if needs_restore:
                logger.info(f"🔄 창 변화 감지 ({', '.join(changes)}): {config.window_title} [{trigger}]")
                logger.info(f"   현재: ({current_rect[0]}, {current_rect[1]}) {current_rect[2] - current_rect[0]}x{current_rect[3] - current_rect[1]}")
                logger.info(f"   목표: ({target_rect[0]}, {target_rect[1]}) {target_rect[2] - target_rect[0]}x{target_rect[3] - target_rect[1]}")
                config.last_change_time = time.time()
                
                # 복구 실행
                if self._restore_window_rect(hwnd, config):
                    self.stats['restorations_performed'] += 1
                    logger.info(f"✅ 창 복구 성공: {config.window_title}")
                else:
                    config.restore_attempts += 1
                    max_attempts_str = "무제한" if config.max_restore_attempts == -1 else str(config.max_restore_attempts)
                    logger.warning(f"❌ 창 복구 실패 ({config.restore_attempts}/{max_attempts_str}): {config.window_title}")
            else:
                # 변화가 없었던 체크
                if trigger == "polling":
                    self.stats['false_positives'] += 1
                    
        except Exception as e:
            logger.error(f"창 상태 확인 오류: {e}")
    
    def _restore_window_rect(self, hwnd: int, config: WindowMonitorConfig) -> bool:
        """창 위치/크기 복구 - 프로필 설정으로 복구"""
        try:
            # 무제한 시도(-1)가 아닌 경우에만 시도 횟수 확인
            if config.max_restore_attempts > 0 and config.restore_attempts >= config.max_restore_attempts:
                logger.warning(f"최대 복구 시도 초과: {config.window_title}")
                return False
            
            # 게임 창에 대해서도 복구 시도 (단, 더 관대한 복구)
            if config.is_game_window:
                logger.info(f"게임 창 복구 시도: {config.window_title}")
                return self._restore_game_window(hwnd, config)
            
            # 직접적인 창 조작으로 복구 (프로필 적용 방식은 무한 루프 위험)
            logger.info(f"직접 복구 시도: {config.window_title}")
            success = self._fallback_restore_window(hwnd, config)
            
            if success:
                logger.info(f"직접 복구 성공: {config.window_title}")
                return True
            else:
                # 다른 방법으로 시도
                logger.warning(f"직접 복구 실패, 향상된 조작으로 시도: {config.window_title}")
                return self._enhanced_restore_window(hwnd, config)
                    
        except Exception as e:
            logger.error(f"창 복구 오류: {e}")
            return False
    
    def _restore_game_window(self, hwnd: int, config: WindowMonitorConfig) -> bool:
        """게임 창 전용 복구 메서드"""
        try:
            logger.info(f"게임 창 복구 시작: {config.window_title}")
            
            # 게임 창의 경우 여러 방법을 순차적으로 시도
            target_rect = config.target_rect
            x, y = target_rect[0], target_rect[1] 
            width = target_rect[2] - target_rect[0]
            height = target_rect[3] - target_rect[1]
            
            # 방법 1: 일시정지 후 MoveWindow
            try:
                import time
                time.sleep(0.1)  # 짧은 대기
                result = win32gui.MoveWindow(hwnd, x, y, width, height, True)
                if result:
                    logger.info(f"게임 창 MoveWindow 복구 성공: {config.window_title}")
                    return True
            except Exception as e:
                logger.debug(f"게임 창 MoveWindow 실패: {e}")
            
            # 방법 2: ShowWindow + MoveWindow 조합
            try:
                import win32con
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.1)
                result = win32gui.MoveWindow(hwnd, x, y, width, height, True)
                if result:
                    logger.info(f"게임 창 ShowWindow+MoveWindow 복구 성공: {config.window_title}")
                    return True
            except Exception as e:
                logger.debug(f"게임 창 ShowWindow+MoveWindow 실패: {e}")
                
            # 방법 3: SetWindowPos 시도
            try:
                result = win32gui.SetWindowPos(
                    hwnd, win32con.HWND_TOP,
                    x, y, width, height,
                    win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
                )
                if result:
                    logger.info(f"게임 창 SetWindowPos 복구 성공: {config.window_title}")
                    return True
            except Exception as e:
                logger.debug(f"게임 창 SetWindowPos 실패: {e}")
            
            # 방법 4: 프로필 적용 시도
            try:
                success = self._apply_profile_settings_to_window(hwnd, config)
                if success:
                    logger.info(f"게임 창 프로필 적용 복구 성공: {config.window_title}")
                    return True
            except Exception as e:
                logger.debug(f"게임 창 프로필 적용 실패: {e}")
            
            # 방법 5: Enhanced Window Manipulator 시도
            try:
                from .enhanced_window_manipulator import get_enhanced_window_manipulator
                manipulator = get_enhanced_window_manipulator()
                result = manipulator.enhanced_move_window(hwnd, x, y, width, height)
                
                if hasattr(result, 'success') and result.success:
                    logger.info(f"게임 창 Enhanced Manipulator 복구 성공: {config.window_title}")
                    return True
                elif result:
                    logger.info(f"게임 창 Enhanced Manipulator 복구 성공: {config.window_title}")
                    return True
            except Exception as e:
                logger.debug(f"게임 창 Enhanced Manipulator 실패: {e}")
            
            # 모든 방법 실패 - 하지만 게임 창은 계속 시도
            logger.warning(f"게임 창 복구 모든 방법 실패, 계속 모니터링: {config.window_title}")
            return False  # 실패했지만 모니터링은 계속
            
        except Exception as e:
            logger.error(f"게임 창 복구 오류: {e}")
            return True  # 게임 창은 오류가 있어도 모니터링 계속
    
    def _apply_profile_settings_to_window(self, hwnd: int, config: WindowMonitorConfig) -> bool:
        """프로필 설정을 창에 적용"""
        try:
            # 프로필 관리자 import
            from .profile_manager import ProfileManager
            
            # 창 정보 준비
            window_info = {
                'hwnd': hwnd,
                'title': config.window_title,
                'process_name': self._get_process_name(hwnd),
                'class_name': self._get_window_class_name(hwnd)
            }
            
            # 프로필 관리자에서 매칭되는 프로필 찾기
            profile_manager = ProfileManager()
            matching_profiles = profile_manager.find_matching_profiles(window_info)
            
            if not matching_profiles:
                logger.debug(f"매칭되는 프로필이 없음: {config.window_title}")
                return False
            
            # 가장 우선순위가 높은 프로필 선택
            profile = matching_profiles[0]  # 이미 priority로 정렬됨
            
            logger.info(f"프로필 '{profile.name}' 적용: {config.window_title}")
            
            # 프로필을 창에 적용 (이것이 실제 창 크기/위치를 변경함)
            success = profile.apply_to_window(window_info)
            
            if success:
                logger.info(f"프로필 적용 성공: {profile.name} -> {config.window_title}")
                return True
            else:
                logger.warning(f"프로필 적용 실패: {profile.name} -> {config.window_title}")
                return False
            
        except Exception as e:
            logger.error(f"프로필 설정 적용 오류: {e}")
            return False
    
    def _enhanced_restore_window(self, hwnd: int, config: WindowMonitorConfig) -> bool:
        """향상된 창 조작을 사용한 복구"""
        try:
            target_rect = config.target_rect
            x, y = target_rect[0], target_rect[1]
            width = target_rect[2] - target_rect[0]
            height = target_rect[3] - target_rect[1]
            
            logger.info(f"향상된 복구 시도: {config.window_title} -> ({x}, {y}) {width}x{height}")
            
            # Enhanced Window Manipulator 사용
            from .enhanced_window_manipulator import get_enhanced_window_manipulator
            manipulator = get_enhanced_window_manipulator()
            
            # 향상된 창 이동 사용
            result = manipulator.enhanced_move_window(hwnd, x, y, width, height)
            
            # 결과 처리
            if hasattr(result, 'success'):
                success = result.success
            else:
                success = bool(result)
            
            if success:
                logger.info(f"향상된 복구 성공: {config.window_title}")
                return True
            else:
                logger.warning(f"향상된 복구 실패: {config.window_title}")
                return False
                
        except Exception as e:
            logger.error(f"향상된 창 복구 오류: {e}")
            return False
    
    def _fallback_restore_window(self, hwnd: int, config: WindowMonitorConfig) -> bool:
        """기본 복구 방법 (target_rect 사용)"""
        try:
            target_rect = config.target_rect
            x, y = target_rect[0], target_rect[1]
            width = target_rect[2] - target_rect[0]
            height = target_rect[3] - target_rect[1]
            
            # MoveWindow 시도
            result = win32gui.MoveWindow(hwnd, x, y, width, height, True)
            
            if result:
                logger.debug(f"기본 창 복구 성공: {config.window_title}")
                return True
            else:
                logger.warning(f"MoveWindow 실패: {config.window_title}")
                
                # 대안으로 SetWindowPos 시도
                try:
                    result = win32gui.SetWindowPos(
                        hwnd, win32con.HWND_TOP,
                        x, y, width, height,
                        win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
                    )
                    return result != 0
                except Exception:
                    return False
                    
        except Exception as e:
            logger.error(f"기본 창 복구 오류: {e}")
            return False
    
    def _get_process_name(self, hwnd: int) -> str:
        """창의 프로세스 이름 가져오기"""
        try:
            import win32process
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
            process_name = win32process.GetModuleFileNameEx(process_handle, 0)
            win32api.CloseHandle(process_handle)
            return os.path.basename(process_name)
        except Exception:
            return ""
    
    def _get_window_class_name(self, hwnd: int) -> str:
        """창의 클래스 이름 가져오기"""
        try:
            return win32gui.GetClassName(hwnd)
        except Exception:
            return ""
    
    def add_window(self, hwnd: int, config: WindowMonitorConfig) -> bool:
        """창 모니터링 추가"""
        try:
            if not win32gui.IsWindow(hwnd):
                logger.error(f"유효하지 않은 창 핸들: {hwnd}")
                return False
            
            config.created_time = time.time()
            config.last_change_time = time.time()
            
            self.monitored_windows[hwnd] = config
            self.window_states[hwnd] = WindowState.NORMAL
            
            # 이벤트 후킹 설정 (아직 설정되지 않았다면)
            if not self.event_hook and config.method in [MonitoringMethod.EVENT_ONLY, MonitoringMethod.HYBRID]:
                self._setup_event_hook()
            
            # 폴링 시작 (필요하다면)
            if config.method in [MonitoringMethod.POLLING_ONLY, MonitoringMethod.HYBRID]:
                self._start_polling_monitor()
            
            logger.info(f"창 모니터링 시작: {config.window_title} [{config.method.value}]")
            return True
            
        except Exception as e:
            logger.error(f"창 모니터링 추가 오류: {e}")
            return False
    
    def _remove_window(self, hwnd: int):
        """창 모니터링 제거"""
        try:
            if hwnd in self.monitored_windows:
                config = self.monitored_windows[hwnd]
                logger.info(f"창 모니터링 제거: {config.window_title}")
                del self.monitored_windows[hwnd]
            
            if hwnd in self.window_states:
                del self.window_states[hwnd]
            
            # 모니터링 중인 창이 없으면 리소스 해제
            if not self.monitored_windows:
                self._cleanup_resources()
                
        except Exception as e:
            logger.error(f"창 모니터링 제거 오류: {e}")
    
    def remove_window(self, hwnd: int) -> bool:
        """외부에서 창 모니터링 제거 요청"""
        self._remove_window(hwnd)
        return True
    
    def remove_all_windows(self):
        """모든 창 모니터링 제거"""
        logger.info("모든 창 모니터링 제거")
        self.monitored_windows.clear()
        self.window_states.clear()
        self._cleanup_resources()
    
    def _cleanup_resources(self):
        """리소스 정리"""
        try:
            # 폴링 중지
            if self.polling_active:
                self.polling_active = False
                self._stop_polling.set()
                
                if self.polling_thread and self.polling_thread.is_alive():
                    self.polling_thread.join(timeout=2.0)
            
            # 이벤트 후킹 해제
            if self.event_hook:
                try:
                    win32gui.UnhookWinEvent(self.event_hook)
                    self.event_hook = None
                    logger.info("이벤트 후킹 해제 완료")
                except Exception as e:
                    logger.warning(f"이벤트 후킹 해제 오류: {e}")
            
            logger.info("모니터링 리소스 정리 완료")
            
        except Exception as e:
            logger.error(f"리소스 정리 오류: {e}")
    
    def get_status(self) -> Dict:
        """현재 상태 반환"""
        monitored_windows = []
        for hwnd, config in self.monitored_windows.items():
            if win32gui.IsWindow(hwnd):
                monitored_windows.append({
                    'hwnd': hwnd,
                    'title': config.window_title,
                    'method': config.method.value,
                    'polling_interval': config.polling_interval,
                    'restore_attempts': config.restore_attempts,
                    'age_seconds': time.time() - config.created_time
                })
        
        return {
            'monitored_count': len(monitored_windows),
            'monitored_windows': monitored_windows,
            'event_hook_active': self.event_hook is not None,
            'polling_active': self.polling_active,
            'quick_response_mode': self.quick_response_mode,
            'stats': self.stats
        }
    
    def __del__(self):
        """소멸자"""
        self.cleanup()
    
    def cleanup(self):
        """정리"""
        self.remove_all_windows()

# 전역 인스턴스
_enhanced_monitor = None

def get_enhanced_monitor() -> EnhancedWindowMonitor:
    """향상된 모니터 인스턴스 반환 (싱글톤)"""
    global _enhanced_monitor
    if _enhanced_monitor is None:
        _enhanced_monitor = EnhancedWindowMonitor()
    return _enhanced_monitor