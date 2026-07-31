"""
통합 마우스 가둠 시스템
=====================

Windows API 기반의 통합된 마우스 가둠 시스템
창 활성화 이벤트 감지를 통한 자동 복구 기능 포함

Key Features:
- ClipCursor API 기반 안정적인 마우스 가둠
- SetWinEventHook을 통한 창 활성화 이벤트 감지
- 자동 마우스 가둠 복구
- 알림창 없는 조용한 동작 (콘솔 로그 + 소리 알림)
- 단일화된 시스템으로 복잡성 제거
"""

import ctypes
from ctypes import wintypes, windll
import win32gui
import win32api
import win32con
import logging
import threading
import time
from typing import Dict, Optional, Tuple, Callable, Set
from dataclasses import dataclass
from enum import Enum
import winsound

logger = logging.getLogger(__name__)

class ConstraintState(Enum):
    """마우스 가둠 상태"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    SUSPENDED = "suspended"  # 일시적으로 중단됨

@dataclass
class ConstraintConfig:
    """마우스 가둠 설정"""
    hwnd: int
    window_title: str
    constraint_rect: Tuple[int, int, int, int]  # (left, top, right, bottom)
    auto_restore: bool = True  # 창 활성화 시 자동 복구
    sound_notification: bool = True
    created_time: float = 0.0

class IntegratedMouseConstraint:
    """통합 마우스 가둠 시스템"""
    
    def __init__(self):
        self.constraints: Dict[int, ConstraintConfig] = {}  # hwnd -> config
        self.current_constraint: Optional[int] = None  # 현재 활성 제약 창 hwnd
        self.state = ConstraintState.INACTIVE
        
        # 폴링 방식 복구 시스템
        self.polling_thread = None
        self.polling_active = False
        self.polling_interval = 0.5  # 500ms 간격
        self._stop_polling = threading.Event()
        
        # 통계
        self.stats = {
            'constraints_applied': 0,
            'constraints_restored': 0,
            'constraint_failures': 0,
            'polling_checks': 0
        }
        
        logger.info("통합 마우스 가둠 시스템 초기화 완료 (폴링 방식)")
    
    def _start_polling_monitor(self):
        """폴링 모니터링 시작"""
        if self.polling_active:
            return
            
        try:
            self.polling_active = True
            self._stop_polling.clear()
            
            self.polling_thread = threading.Thread(
                target=self._polling_worker,
                name="MouseConstraintPoller",
                daemon=True
            )
            self.polling_thread.start()
            
            logger.info("마우스 가둠 폴링 모니터링 시작")
            
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
            
            logger.info("마우스 가둠 폴링 모니터링 중지")
            
        except Exception as e:
            logger.error(f"폴링 모니터링 중지 오류: {e}")
    
    def _polling_worker(self):
        """폴링 워커 스레드"""
        logger.info("폴링 워커 스레드 시작")
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
                            current_title = win32gui.GetWindowText(current_foreground)
                            logger.debug(f"포커스 변경 감지: {current_title} (hwnd: {current_foreground})")
                            
                            # 제약 설정된 창으로 포커스가 돌아왔는지 확인
                            if current_foreground in self.constraints:
                                config = self.constraints[current_foreground]
                                
                                if config.auto_restore:
                                    logger.info(f"제약 창으로 포커스 복귀: {config.window_title}")
                                    
                                    # 마우스 가둠 복구
                                    if self._restore_mouse_constraint(current_foreground):
                                        logger.info(f"마우스 가둠 자동 복구 성공: {config.window_title}")
                                        self.stats['constraints_restored'] += 1
                                        
                                        # 소리 알림
                                        if config.sound_notification:
                                            self._play_sound_notification("restore")
                                    else:
                                        logger.warning(f"마우스 가둠 자동 복구 실패: {config.window_title}")
                            
                            # 다른 창으로 포커스가 이동했을 때 상태 업데이트
                            elif (self.current_constraint and 
                                  self.current_constraint != current_foreground and
                                  self.state == ConstraintState.ACTIVE):
                                logger.debug(f"다른 창으로 포커스 이동, 제약 일시 중단")
                                self.state = ConstraintState.SUSPENDED
                        
                        last_foreground_hwnd = current_foreground
                    
                    # 폴링 간격 대기
                    if self._stop_polling.wait(self.polling_interval):
                        break
                        
                except Exception as e:
                    logger.error(f"폴링 워커 오류: {e}")
                    time.sleep(1.0)  # 오류 시 더 긴 대기
            
        except Exception as e:
            logger.error(f"폴링 워커 심각한 오류: {e}")
        finally:
            logger.info(f"폴링 워커 종료 (총 {self.stats['polling_checks']}회 체크)")
    
    def apply_constraint(self, hwnd: int, auto_restore: bool = True, sound_notification: bool = True) -> bool:
        """
        마우스 가둠 적용
        
        Args:
            hwnd: 창 핸들
            auto_restore: 창 활성화 시 자동 복구 여부
            sound_notification: 소리 알림 여부
        
        Returns:
            bool: 성공 여부
        """
        try:
            if not win32gui.IsWindow(hwnd):
                logger.error(f"잘못된 창 핸들: {hwnd}")
                return False
            
            # 창 정보 가져오기
            window_title = win32gui.GetWindowText(hwnd)
            window_rect = win32gui.GetWindowRect(hwnd)
            
            # 최소화된 창 처리
            if window_rect[0] <= -30000 or window_rect[1] <= -30000:
                logger.warning(f"창이 최소화되어 있음, 복원 시도: {window_title}")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)
                window_rect = win32gui.GetWindowRect(hwnd)
                
                if window_rect[0] <= -30000 or window_rect[1] <= -30000:
                    logger.error(f"창 복원 실패: {window_title}")
                    return False
            
            logger.info(f"마우스 가둠 적용 시작: {window_title}")
            logger.info(f"창 영역: {window_rect}")
            
            # ClipCursor 적용
            result = win32api.ClipCursor(window_rect)
            
            # ClipCursor 결과 검증
            if result is None:
                # None 반환값도 성공일 수 있으므로 실제 테스트
                success = self._test_constraint_effectiveness(window_rect)
            else:
                success = (result != 0)
            
            if success:
                # 제약 설정 저장
                config = ConstraintConfig(
                    hwnd=hwnd,
                    window_title=window_title,
                    constraint_rect=window_rect,
                    auto_restore=auto_restore,
                    sound_notification=sound_notification,
                    created_time=time.time()
                )
                
                self.constraints[hwnd] = config
                self.current_constraint = hwnd
                self.state = ConstraintState.ACTIVE
                self.stats['constraints_applied'] += 1
                
                # 폴링 모니터링 시작 (자동 복구 기능)
                if auto_restore:
                    self._start_polling_monitor()
                
                logger.info(f"마우스 가둠 적용 성공: {window_title}")
                
                # 소리 알림
                if sound_notification:
                    self._play_sound_notification("applied")
                
                return True
            else:
                logger.error(f"ClipCursor 적용 실패: {window_title}")
                self.stats['constraint_failures'] += 1
                return False
                
        except Exception as e:
            logger.error(f"마우스 가둠 적용 오류: {e}")
            self.stats['constraint_failures'] += 1
            return False
    
    def _test_constraint_effectiveness(self, rect: Tuple[int, int, int, int]) -> bool:
        """마우스 가둠 효과 테스트"""
        try:
            # 현재 마우스 위치 저장
            original_pos = win32gui.GetCursorPos()
            
            # 경계 밖으로 이동 시도
            test_x = rect[2] + 20  # right + 20
            test_y = rect[3] + 20  # bottom + 20
            
            win32api.SetCursorPos((test_x, test_y))
            time.sleep(0.05)
            
            new_pos = win32gui.GetCursorPos()
            
            # 원래 위치로 복원
            win32api.SetCursorPos(original_pos)
            
            # 경계 밖으로 나가지 못했으면 성공
            constrained = (new_pos[0] != test_x or new_pos[1] != test_y)
            
            if constrained:
                logger.info(f"마우스 가둠 효과 확인됨: 시도 위치 ({test_x}, {test_y}), 실제 위치 {new_pos}")
            else:
                logger.warning(f"마우스 가둠 효과 없음: 시도 위치 ({test_x}, {test_y}), 실제 위치 {new_pos}")
            
            return constrained
            
        except Exception as e:
            logger.error(f"마우스 가둠 효과 테스트 오류: {e}")
            return False
    
    def _restore_mouse_constraint(self, hwnd: int) -> bool:
        """마우스 가둠 복구"""
        try:
            if hwnd not in self.constraints:
                return False
            
            config = self.constraints[hwnd]
            
            # 창이 여전히 존재하는지 확인
            if not win32gui.IsWindow(hwnd):
                logger.info(f"창이 더 이상 존재하지 않음, 제약 제거: {config.window_title}")
                self.remove_constraint(hwnd)
                return False
            
            # 현재 창 영역 가져오기 (창 크기가 변경되었을 수 있음)
            current_rect = win32gui.GetWindowRect(hwnd)
            
            # 제약 영역 업데이트
            config.constraint_rect = current_rect
            
            # ClipCursor 재적용
            result = win32api.ClipCursor(current_rect)
            
            if result is None:
                success = self._test_constraint_effectiveness(current_rect)
            else:
                success = (result != 0)
            
            if success:
                self.current_constraint = hwnd
                self.state = ConstraintState.ACTIVE
                logger.info(f"마우스 가둠 복구 성공: {config.window_title}")
                return True
            else:
                logger.error(f"마우스 가둠 복구 실패: {config.window_title}")
                return False
                
        except Exception as e:
            logger.error(f"마우스 가둠 복구 오류: {e}")
            return False
    
    def remove_constraint(self, hwnd: Optional[int] = None) -> bool:
        """
        마우스 가둠 제거
        
        Args:
            hwnd: 특정 창 핸들 (None이면 모든 제약 제거)
        
        Returns:
            bool: 성공 여부
        """
        try:
            if hwnd is None:
                # 모든 제약 제거
                logger.info("모든 마우스 가둠 제거")
                
                # ClipCursor 해제 (전체 화면으로)
                screen_width = win32api.GetSystemMetrics(0)
                screen_height = win32api.GetSystemMetrics(1)
                full_screen = (0, 0, screen_width, screen_height)
                
                result = win32api.ClipCursor(full_screen)
                
                self.constraints.clear()
                self.current_constraint = None
                self.state = ConstraintState.INACTIVE
                
                # 폴링 모니터링 중지
                self._stop_polling_monitor()
                
                logger.info("모든 마우스 가둠 해제 완료")
                return True
            else:
                # 특정 창 제약 제거
                if hwnd in self.constraints:
                    config = self.constraints[hwnd]
                    logger.info(f"마우스 가둠 제거: {config.window_title}")
                    
                    del self.constraints[hwnd]
                    
                    # 현재 활성 제약이었다면 해제
                    if self.current_constraint == hwnd:
                        screen_width = win32api.GetSystemMetrics(0)
                        screen_height = win32api.GetSystemMetrics(1)
                        full_screen = (0, 0, screen_width, screen_height)
                        
                        win32api.ClipCursor(full_screen)
                        self.current_constraint = None
                        self.state = ConstraintState.INACTIVE
                        
                        # 더 이상 제약이 없으면 폴링 중지
                        if not self.constraints:
                            self._stop_polling_monitor()
                    
                    return True
                else:
                    logger.warning(f"제거할 제약을 찾을 수 없음: {hwnd}")
                    return False
                    
        except Exception as e:
            logger.error(f"마우스 가둠 제거 오류: {e}")
            return False
    
    def _play_sound_notification(self, event_type: str):
        """소리 알림 재생"""
        # 소리 알림이 비활성화된 경우 무시
        return
        
        # 아래 코드는 더 이상 실행되지 않음 (소리 비활성화)
        try:
            if event_type == "applied":
                # 마우스 가둠 적용 시 - 상승 톤
                winsound.Beep(800, 200)
            elif event_type == "restore":
                # 자동 복구 시 - 짧은 삐삐
                winsound.Beep(600, 100)
                time.sleep(0.05)
                winsound.Beep(600, 100)
            elif event_type == "removed":
                # 제거 시 - 하강 톤
                winsound.Beep(600, 200)
        except:
            # 소리 재생 실패해도 무시
            pass
    
    def get_status(self) -> Dict:
        """현재 상태 반환"""
        active_constraints = []
        for hwnd, config in self.constraints.items():
            if win32gui.IsWindow(hwnd):
                active_constraints.append({
                    'hwnd': hwnd,
                    'title': config.window_title,
                    'rect': config.constraint_rect,
                    'auto_restore': config.auto_restore,
                    'age_seconds': time.time() - config.created_time
                })
        
        return {
            'state': self.state.value,
            'current_constraint': self.current_constraint,
            'active_constraints': active_constraints,
            'constraint_count': len(active_constraints),
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
            # 모든 마우스 가둠 해제
            self.remove_constraint()
            
            # 폴링 모니터링 중지
            self._stop_polling_monitor()
                    
        except Exception as e:
            logger.error(f"리소스 정리 오류: {e}")

# 전역 인스턴스
_integrated_constraint = None

def get_integrated_constraint() -> IntegratedMouseConstraint:
    """통합 마우스 가둠 시스템 인스턴스 반환 (싱글톤)"""
    global _integrated_constraint
    if _integrated_constraint is None:
        _integrated_constraint = IntegratedMouseConstraint()
    return _integrated_constraint

def test_integrated_constraint():
    """통합 시스템 테스트"""
    print("=== 통합 마우스 가둠 시스템 테스트 ===")
    
    try:
        constraint = get_integrated_constraint()
        
        # 활성 창 가져오기
        active_hwnd = win32gui.GetForegroundWindow()
        if not active_hwnd:
            print("활성 창을 찾을 수 없습니다.")
            return False
        
        title = win32gui.GetWindowText(active_hwnd)
        print(f"테스트 대상: {title} (hwnd: {active_hwnd})")
        
        # 마우스 가둠 적용
        print("마우스 가둠 적용 중...")
        success = constraint.apply_constraint(active_hwnd)
        
        if success:
            print("✓ 마우스 가둠 적용 성공")
            
            # 5초 대기
            print("5초 대기 중... (다른 창으로 전환해보세요)")
            time.sleep(5)
            
            # 상태 확인
            status = constraint.get_status()
            print(f"현재 상태: {status}")
            
            # 제거
            print("마우스 가둠 제거 중...")
            constraint.remove_constraint(active_hwnd)
            print("✓ 테스트 완료")
            
            return True
        else:
            print("✗ 마우스 가둠 적용 실패")
            return False
            
    except Exception as e:
        print(f"테스트 오류: {e}")
        return False

if __name__ == "__main__":
    test_integrated_constraint()