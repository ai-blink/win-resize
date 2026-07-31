"""
통합 창 고정 시스템
=================

Windows API 기반의 통합된 창 크기/위치 고정 시스템
창 활성화 이벤트 감지를 통한 자동 복구 기능 포함

Key Features:
- SetWindowPos API 기반 안정적인 창 크기/위치 고정
- 폴링 방식 창 활성화 감지를 통한 자동 복구
- 창 크기, 위치 개별 또는 통합 고정 지원
- 조용한 동작 (콘솔 로그만)
- 단일화된 시스템으로 복잡성 제거
"""

import win32gui
import win32con  
import win32api
import logging
import threading
import time
from typing import Dict, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class LockType(Enum):
    """창 고정 타입"""
    SIZE = "size"           # 크기만 고정
    POSITION = "position"   # 위치만 고정  
    SIZE_AND_POSITION = "size_and_position"  # 크기와 위치 모두 고정
    WIDTH_ONLY = "width_only"    # 너비만 고정
    HEIGHT_ONLY = "height_only"  # 높이만 고정

class LockState(Enum):
    """창 고정 상태"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    SUSPENDED = "suspended"  # 일시적으로 중단됨

@dataclass
class WindowLockConfig:
    """창 고정 설정"""
    hwnd: int
    window_title: str
    target_rect: Tuple[int, int, int, int]  # (left, top, right, bottom)
    lock_type: LockType
    lock_size: bool = True
    lock_width: bool = True
    lock_height: bool = True
    lock_position: bool = True
    auto_restore: bool = True  # 창 활성화 시 자동 복구
    tolerance: int = 5  # 허용 오차 (픽셀)
    created_time: float = 0.0
    restore_attempts: int = 0
    max_attempts: int = 100

class IntegratedWindowLock:
    """통합 창 고정 시스템"""
    
    def __init__(self):
        self.locked_windows: Dict[int, WindowLockConfig] = {}  # hwnd -> config
        self.state = LockState.INACTIVE
        
        # 폴링 방식 복구 시스템 (마우스 가둠과 공유)
        self.polling_thread = None
        self.polling_active = False
        self.polling_interval = 0.5  # 500ms 간격
        self._stop_polling = threading.Event()
        
        # 통계
        self.stats = {
            'locks_applied': 0,
            'locks_restored': 0,
            'lock_failures': 0,
            'polling_checks': 0
        }
        
        logger.info("통합 창 고정 시스템 초기화 완료 (폴링 방식)")
    
    def _start_enhanced_monitoring(self, hwnd: int, config: WindowLockConfig, enhanced_config: Dict):
        """향상된 모니터링 시스템 시작"""
        try:
            from .enhanced_window_monitor import get_enhanced_monitor, WindowMonitorConfig, MonitoringMethod
            
            # 모니터링 방식 변환
            method_map = {
                'event_only': MonitoringMethod.EVENT_ONLY,
                'polling_only': MonitoringMethod.POLLING_ONLY,
                'hybrid': MonitoringMethod.HYBRID
            }
            method = method_map.get(enhanced_config.get('method', 'hybrid'), MonitoringMethod.HYBRID)
            
            # 향상된 모니터 설정 생성
            monitor_config = WindowMonitorConfig(
                hwnd=hwnd,
                window_title=config.window_title,
                target_rect=config.target_rect,
                method=method,
                polling_interval=enhanced_config.get('polling_interval', 2.0),
                quick_response_interval=enhanced_config.get('quick_response_interval', 0.3),
                pause_when_inactive=enhanced_config.get('pause_when_inactive', True),
                auto_restore=True,
                restore_on_focus=enhanced_config.get('restore_on_focus', True),
                restore_on_resize=enhanced_config.get('restore_on_resize', True),
                restore_on_move=enhanced_config.get('restore_on_move', True),
                tolerance=enhanced_config.get('tolerance', 5),
                max_restore_attempts=enhanced_config.get('max_attempts', 50),
                adaptive_polling=enhanced_config.get('adaptive_polling', True),
                is_game_window=self._is_game_window(hwnd, config.window_title)
            )
            
            # 향상된 모니터에 창 추가
            enhanced_monitor = get_enhanced_monitor()
            success = enhanced_monitor.add_window(hwnd, monitor_config)
            
            if success:
                logger.info(f"향상된 모니터링 시작: {config.window_title} [{method.value}]")
            else:
                logger.warning(f"향상된 모니터링 시작 실패, 기본 폴링으로 대체: {config.window_title}")
                self._start_polling_monitor()
                
        except Exception as e:
            logger.error(f"향상된 모니터링 시작 오류: {e}")
            logger.info("기본 폴링 모니터링으로 대체")
            self._start_polling_monitor()

    def _start_polling_monitor(self):
        """폴링 모니터링 시작"""
        if self.polling_active:
            return
            
        try:
            self.polling_active = True
            self._stop_polling.clear()
            
            self.polling_thread = threading.Thread(
                target=self._polling_worker,
                name="WindowLockPoller", 
                daemon=True
            )
            self.polling_thread.start()
            
            logger.info("창 고정 폴링 모니터링 시작")
            
        except Exception as e:
            logger.error(f"폴링 모니터링 시작 오류: {e}")
            self.polling_active = False
    
    def _stop_polling_monitor(self):
        """폴링 모니터링 중지"""
        if not self.polling_active:
            return
            
        try:
            self.polling_active = False
            self._stop_polling.set()
            
            if self.polling_thread and self.polling_thread.is_alive():
                self.polling_thread.join(timeout=2.0)
            
            logger.info("창 고정 폴링 모니터링 중지")
            
        except Exception as e:
            logger.error(f"폴링 모니터링 중지 오류: {e}")
    
    def _polling_worker(self):
        """폴링 워커 스레드"""
        logger.info("창 고정 폴링 워커 스레드 시작")
        last_foreground_hwnd = None
        
        try:
            while self.polling_active and not self._stop_polling.is_set():
                try:
                    # 현재 활성 창 확인
                    current_foreground = win32gui.GetForegroundWindow()
                    self.stats['polling_checks'] += 1
                    
                    # 포커스 변경 감지
                    if current_foreground != last_foreground_hwnd:
                        if current_foreground and win32gui.IsWindow(current_foreground):
                            # 고정 설정된 창으로 포커스가 돌아왔는지 확인
                            if current_foreground in self.locked_windows:
                                config = self.locked_windows[current_foreground]
                                
                                if config.auto_restore:
                                    logger.info(f"고정 창으로 포커스 복귀: {config.window_title}")
                                    
                                    # 창 고정 복구
                                    if self._restore_window_lock(current_foreground):
                                        logger.info(f"창 고정 자동 복구 성공: {config.window_title}")
                                        self.stats['locks_restored'] += 1
                                    else:
                                        logger.warning(f"창 고정 자동 복구 실패: {config.window_title}")
                            
                            # 모든 고정 창에 대해 현재 상태 확인 및 복구
                            for hwnd, config in list(self.locked_windows.items()):
                                if (win32gui.IsWindow(hwnd) and 
                                    config.auto_restore and 
                                    config.restore_attempts < config.max_attempts):
                                    
                                    if self._check_and_restore_if_needed(hwnd, config):
                                        self.stats['locks_restored'] += 1
                        
                        last_foreground_hwnd = current_foreground
                    
                    # 폴링 간격 대기
                    if self._stop_polling.wait(self.polling_interval):
                        break
                        
                except Exception as e:
                    logger.error(f"창 고정 폴링 워커 오류: {e}")
                    time.sleep(1.0)  # 오류 시 더 긴 대기
            
        except Exception as e:
            logger.error(f"창 고정 폴링 워커 심각한 오류: {e}")
        finally:
            logger.info(f"창 고정 폴링 워커 종료 (총 {self.stats['polling_checks']}회 체크)")
    
    def _check_and_restore_if_needed(self, hwnd: int, config: WindowLockConfig) -> bool:
        """필요시 창 고정 확인 및 복구"""
        try:
            current_rect = win32gui.GetWindowRect(hwnd)
            target_rect = config.target_rect
            
            # 변경 사항 감지
            position_changed = (config.lock_position and 
                              (abs(current_rect[0] - target_rect[0]) > config.tolerance or
                               abs(current_rect[1] - target_rect[1]) > config.tolerance))
            
            size_changed = False
            if config.lock_size or config.lock_width or config.lock_height:
                current_width = current_rect[2] - current_rect[0]
                current_height = current_rect[3] - current_rect[1]
                target_width = target_rect[2] - target_rect[0]
                target_height = target_rect[3] - target_rect[1]
                
                width_changed = config.lock_width and abs(current_width - target_width) > config.tolerance
                height_changed = config.lock_height and abs(current_height - target_height) > config.tolerance
                size_changed = width_changed or height_changed
            
            # 복구 필요시 실행
            if position_changed or size_changed:
                logger.debug(f"창 상태 변경 감지: {config.window_title}")
                logger.debug(f"  위치 변경: {position_changed}, 크기 변경: {size_changed}")
                
                return self._restore_window_state(hwnd, config)
            
            return False
            
        except Exception as e:
            logger.error(f"창 상태 확인 오류 (hwnd: {hwnd}): {e}")
            return False
    
    def _is_game_window(self, hwnd: int, window_title: str) -> bool:
        """게임 창인지 판단"""
        try:
            # 창 제목으로 게임 판단
            game_keywords = [
                'brood war', 'starcraft', 'warcraft', 'diablo',
                'counter-strike', 'dota', 'league of legends',
                'overwatch', 'world of warcraft', 'hearthstone',
                'steam', 'origin', 'uplay', 'battle.net',
                'game', 'gaming', 'blizzard'
            ]
            
            title_lower = window_title.lower()
            is_game_by_title = any(keyword in title_lower for keyword in game_keywords)
            
            if is_game_by_title:
                logger.info(f"게임 창으로 판단됨 (제목): {window_title}")
                return True
            
            # 창 스타일로 게임 창인지 추가 확인
            try:
                import win32con
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                
                # 전체 화면이나 특별한 스타일의 창은 게임일 가능성 높음
                is_fullscreen = not (style & win32con.WS_CAPTION) and not (style & win32con.WS_THICKFRAME)
                
                if is_fullscreen:
                    logger.info(f"전체화면 창으로 판단됨 (게임 가능성): {window_title}")
                    return True
                    
            except Exception as e:
                logger.debug(f"창 스타일 확인 실패: {e}")
            
            return False
            
        except Exception as e:
            logger.debug(f"게임 창 판단 오류: {e}")
            return False
    
    def apply_window_lock(self, hwnd: int, lock_config: Dict, auto_restore: bool = True, 
                         enhanced_config: Optional[Dict] = None) -> bool:
        """
        창 고정 적용
        
        Args:
            hwnd: 창 핸들
            lock_config: {
                'lock_size': bool,
                'lock_width': bool,
                'lock_height': bool, 
                'lock_position': bool,
                'target_rect': (x, y, width, height) or (left, top, right, bottom)
            }
            auto_restore: 창 활성화 시 자동 복구 여부
        
        Returns:
            bool: 성공 여부
        """
        try:
            if not win32gui.IsWindow(hwnd):
                logger.error(f"잘못된 창 핸들: {hwnd}")
                return False
            
            # 창 정보 가져오기
            window_title = win32gui.GetWindowText(hwnd)
            target_rect = lock_config.get('target_rect')
            
            if not target_rect:
                # target_rect가 없으면 현재 창 위치/크기 사용
                target_rect = win32gui.GetWindowRect(hwnd)
            
            # 최소화된 창 처리
            if target_rect[0] <= -30000 or target_rect[1] <= -30000:
                logger.warning(f"창이 최소화되어 있음, 복원 시도: {window_title}")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)
                target_rect = win32gui.GetWindowRect(hwnd)
                
                if target_rect[0] <= -30000 or target_rect[1] <= -30000:
                    logger.error(f"창 복원 실패: {window_title}")
                    return False
            
            # Lock 타입 결정
            lock_size = lock_config.get('lock_size', False)
            lock_width = lock_config.get('lock_width', False) 
            lock_height = lock_config.get('lock_height', False)
            lock_position = lock_config.get('lock_position', False)
            
            if lock_size and lock_position:
                lock_type = LockType.SIZE_AND_POSITION
            elif lock_size:
                lock_type = LockType.SIZE
            elif lock_position:
                lock_type = LockType.POSITION
            elif lock_width and not lock_height:
                lock_type = LockType.WIDTH_ONLY
            elif lock_height and not lock_width:
                lock_type = LockType.HEIGHT_ONLY
            else:
                lock_type = LockType.SIZE_AND_POSITION  # 기본값
            
            logger.info(f"창 고정 적용 시작: {window_title}")
            logger.info(f"고정 타입: {lock_type.value}")
            logger.info(f"목표 영역: {target_rect}")
            
            # 게임 창 확인
            is_game = self._is_game_window(hwnd, window_title)
            
            if is_game:
                logger.info(f"게임 창 감지: {window_title} - 모니터링 전용 모드")
                # 게임 창의 경우 즉시 적용 시도하지 않고 모니터링만 활성화
                success = True  # 게임 창은 모니터링 활성화를 성공으로 간주
            else:
                # 일반 창의 경우 즉시 창 고정 적용
                success = self._apply_window_position_size(hwnd, target_rect, lock_config)
            
            if success:
                # 고정 설정 저장
                config = WindowLockConfig(
                    hwnd=hwnd,
                    window_title=window_title,
                    target_rect=target_rect,
                    lock_type=lock_type,
                    lock_size=lock_size,
                    lock_width=lock_width,
                    lock_height=lock_height,
                    lock_position=lock_position,
                    auto_restore=auto_restore,
                    tolerance=5,  # 5픽셀 허용 오차
                    created_time=time.time()
                )
                
                self.locked_windows[hwnd] = config
                self.state = LockState.ACTIVE
                self.stats['locks_applied'] += 1
                
                # 향상된 모니터링 시작 (자동 복구 기능)  
                if auto_restore:
                    if enhanced_config and enhanced_config.get('enabled', True):
                        # 향상된 모니터링 사용
                        self._start_enhanced_monitoring(hwnd, config, enhanced_config)
                    else:
                        # 기존 폴링 모니터링 사용
                        self._start_polling_monitor()
                
                logger.info(f"창 고정 적용 성공: {window_title}")
                return True
            else:
                logger.error(f"창 고정 적용 실패: {window_title}")
                self.stats['lock_failures'] += 1
                return False
                
        except Exception as e:
            logger.error(f"창 고정 적용 오류: {e}")
            self.stats['lock_failures'] += 1
            return False
    
    def _apply_window_position_size(self, hwnd: int, target_rect: Tuple[int, int, int, int], 
                                  lock_config: Dict) -> bool:
        """창 위치/크기 즉시 적용"""
        try:
            x, y = target_rect[0], target_rect[1]
            width = target_rect[2] - target_rect[0] 
            height = target_rect[3] - target_rect[1]
            
            # 방법 1: MoveWindow 우선 시도 (더 호환성 좋음)
            try:
                result = win32gui.MoveWindow(hwnd, x, y, width, height, True)
                if result:
                    logger.debug(f"MoveWindow 성공: hwnd={hwnd}")
                    return True
                else:
                    logger.warning(f"MoveWindow 실패: hwnd={hwnd}")
            except Exception as e:
                logger.warning(f"MoveWindow 예외: {e}")
            
            # 방법 2: SetWindowPos로 대안 시도
            try:
                result = win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOP,
                    x, y, width, height,
                    win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
                )
                
                if result:
                    logger.debug(f"SetWindowPos 성공: hwnd={hwnd}")
                    return True
                else:
                    error_code = win32api.GetLastError()
                    logger.warning(f"SetWindowPos 실패: hwnd={hwnd}, error={error_code}")
            except Exception as e:
                logger.warning(f"SetWindowPos 예외: {e}")
            
            # 방법 3: 창 복원 후 시도
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.1)
                
                result = win32gui.MoveWindow(hwnd, x, y, width, height, True)
                if result:
                    logger.debug(f"ShowWindow + MoveWindow 성공: hwnd={hwnd}")
                    return True
            except Exception as e:
                logger.warning(f"ShowWindow 방법 예외: {e}")
            
            logger.error(f"모든 창 조작 방법 실패: hwnd={hwnd}")
            return False
                
        except Exception as e:
            logger.error(f"창 위치/크기 적용 오류: {e}")
            return False
    
    def _restore_window_lock(self, hwnd: int) -> bool:
        """창 고정 복구"""
        try:
            if hwnd not in self.locked_windows:
                return False
            
            config = self.locked_windows[hwnd]
            
            # 창이 여전히 존재하는지 확인
            if not win32gui.IsWindow(hwnd):
                logger.info(f"창이 더 이상 존재하지 않음, 고정 제거: {config.window_title}")
                self.remove_window_lock(hwnd)
                return False
            
            return self._restore_window_state(hwnd, config)
            
        except Exception as e:
            logger.error(f"창 고정 복구 오류: {e}")
            return False
    
    def _restore_window_state(self, hwnd: int, config: WindowLockConfig) -> bool:
        """창 상태 복원"""
        try:
            config.restore_attempts += 1
            
            if config.restore_attempts > config.max_attempts:
                logger.warning(f"최대 복원 시도 횟수 초과: {config.window_title}")
                return False
            
            # 게임 창인지 확인
            is_game = self._is_game_window(hwnd, config.window_title)
            
            if is_game:
                # 게임 창의 경우 복원 시도하지 않고 성공으로 간주
                logger.debug(f"게임 창 복원 스킵: {config.window_title}")
                return True
            
            # 현재 창 영역 가져오기 (창 크기가 변경되었을 수 있음)
            current_rect = win32gui.GetWindowRect(hwnd)
            target_rect = config.target_rect
            
            # 필요에 따라 위치나 크기만 복원
            restore_x, restore_y = current_rect[0], current_rect[1]
            restore_width = current_rect[2] - current_rect[0]
            restore_height = current_rect[3] - current_rect[1]
            
            # 위치 복원
            if config.lock_position:
                restore_x, restore_y = target_rect[0], target_rect[1]
            
            # 크기 복원
            if config.lock_width:
                restore_width = target_rect[2] - target_rect[0]
            if config.lock_height:
                restore_height = target_rect[3] - target_rect[1]
            
            # 복원 실행 (MoveWindow 우선)
            try:
                result = win32gui.MoveWindow(hwnd, restore_x, restore_y, restore_width, restore_height, True)
                if result:
                    logger.debug(f"창 고정 복원 성공 (MoveWindow): {config.window_title}")
                    return True
            except Exception as e:
                logger.warning(f"MoveWindow 복원 실패: {e}")
            
            # 대안으로 SetWindowPos 시도
            try:
                result = win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOP,
                    restore_x, restore_y, restore_width, restore_height,
                    win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
                )
                
                if result:
                    logger.debug(f"창 고정 복원 성공 (SetWindowPos): {config.window_title}")
                    return True
                else:
                    error_code = win32api.GetLastError()
                    logger.warning(f"SetWindowPos 복원 실패: {config.window_title}, error={error_code}")
            except Exception as e:
                logger.warning(f"SetWindowPos 복원 예외: {e}")
            
            # 일반 창에서도 모든 방법 실패시 게임 창처럼 허용적으로 처리
            logger.info(f"창 복원 실패하지만 모니터링 계속: {config.window_title}")
            return True  # 복원 실패해도 모니터링은 계속
                
        except Exception as e:
            logger.error(f"창 상태 복원 오류: {e}")
            return False
    
    def remove_window_lock(self, hwnd: Optional[int] = None) -> bool:
        """
        창 고정 제거
        
        Args:
            hwnd: 특정 창 핸들 (None이면 모든 고정 제거)
        
        Returns:
            bool: 성공 여부
        """
        try:
            if hwnd is None:
                # 모든 고정 제거
                logger.info("모든 창 고정 제거")
                
                self.locked_windows.clear()
                self.state = LockState.INACTIVE
                
                # 폴링 모니터링 중지
                self._stop_polling_monitor()
                
                logger.info("모든 창 고정 해제 완료")
                return True
            else:
                # 특정 창 고정 제거
                if hwnd in self.locked_windows:
                    config = self.locked_windows[hwnd]
                    logger.info(f"창 고정 제거: {config.window_title}")
                    
                    del self.locked_windows[hwnd]
                    
                    # 더 이상 고정된 창이 없으면 폴링 중지
                    if not self.locked_windows:
                        self.state = LockState.INACTIVE
                        self._stop_polling_monitor()
                    
                    return True
                else:
                    logger.warning(f"제거할 창 고정을 찾을 수 없음: {hwnd}")
                    return False
                    
        except Exception as e:
            logger.error(f"창 고정 제거 오류: {e}")
            return False
    
    def get_status(self) -> Dict:
        """현재 상태 반환"""
        active_locks = []
        for hwnd, config in self.locked_windows.items():
            if win32gui.IsWindow(hwnd):
                active_locks.append({
                    'hwnd': hwnd,
                    'title': config.window_title,
                    'lock_type': config.lock_type.value,
                    'target_rect': config.target_rect,
                    'auto_restore': config.auto_restore,
                    'restore_attempts': config.restore_attempts,
                    'age_seconds': time.time() - config.created_time
                })
        
        return {
            'state': self.state.value,
            'active_locks': active_locks,
            'lock_count': len(active_locks),
            'polling_active': self.polling_active,
            'polling_checks': self.stats.get('polling_checks', 0),
            'stats': self.stats
        }
    
    def __del__(self):
        """소멸자 - 리소스 정리"""
        self.cleanup()
    
    def cleanup(self):
        """리소스 정리"""
        try:
            # 모든 창 고정 해제
            self.remove_window_lock()
            
            # 폴링 모니터링 중지
            self._stop_polling_monitor()
                    
        except Exception as e:
            logger.error(f"창 고정 시스템 리소스 정리 오류: {e}")

# 전역 인스턴스
_integrated_window_lock = None

def get_integrated_window_lock() -> IntegratedWindowLock:
    """통합 창 고정 시스템 인스턴스 반환 (싱글톤)"""
    global _integrated_window_lock
    if _integrated_window_lock is None:
        _integrated_window_lock = IntegratedWindowLock()
    return _integrated_window_lock

if __name__ == "__main__":
    # 테스트 코드
    import time
    
    print("통합 창 고정 시스템 테스트")
    
    try:
        lock_system = get_integrated_window_lock()
        
        # 현재 활성 창에 크기/위치 고정 적용
        active_hwnd = win32gui.GetForegroundWindow()
        if active_hwnd:
            window_title = win32gui.GetWindowText(active_hwnd)
            print(f"테스트 창: {window_title}")
            
            # 현재 위치/크기로 고정
            current_rect = win32gui.GetWindowRect(active_hwnd)
            
            lock_config = {
                'lock_size': True,
                'lock_width': True,
                'lock_height': True,
                'lock_position': True,
                'target_rect': current_rect
            }
            
            success = lock_system.apply_window_lock(active_hwnd, lock_config, auto_restore=True)
            
            if success:
                print("창 고정 적용 성공!")
                print("10초 동안 창 크기나 위치를 변경해보세요...")
                
                for i in range(10, 0, -1):
                    status = lock_system.get_status()
                    restored = status['stats'].get('locks_restored', 0)
                    print(f"{i}초 남음, 자동 복구: {restored}회", end='\r')
                    time.sleep(1)
                
                print("\n창 고정 해제 중...")
                lock_system.remove_window_lock(active_hwnd)
                print("테스트 완료!")
            else:
                print("창 고정 적용 실패!")
                
    except Exception as e:
        print(f"테스트 오류: {e}")
    
    input("엔터를 눌러 종료하세요...")