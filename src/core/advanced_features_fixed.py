"""
Advanced Features Fixed Implementation
=====================================

창 크기 고정과 마우스 가둠 기능의 수정된 구현
Windows API 제약 사항을 고려한 안정적인 대안 제공
"""

import logging
import time
import threading
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# Import game handler for special game window processing
try:
    from .game_window_handler import get_game_handler
    GAME_HANDLER_AVAILABLE = True
except ImportError:
    GAME_HANDLER_AVAILABLE = False
    logger.warning("Game handler not available")


class AdvancedWindowFeatures:
    """고급 창 기능의 안정적인 구현"""
    
    def __init__(self):
        self.monitoring_threads = {}  # hwnd -> thread
        self.constrained_windows = set()
        self.locked_windows = {}  # hwnd -> config
        self.running = True
    
    def apply_mouse_constraint(self, hwnd: int, mode: str = "strict") -> bool:
        """
        마우스 가둠 기능 - 통합 시스템 사용
        
        Args:
            hwnd: 창 핸들
            mode: "strict" 또는 "soft"
        """
        try:
            import win32gui
            from .integrated_mouse_constraint import get_integrated_constraint
            
            if not win32gui.IsWindow(hwnd):
                logger.error(f"Invalid window handle: {hwnd}")
                return False
            
            title = win32gui.GetWindowText(hwnd)
            logger.info(f"통합 마우스 가둠 시스템으로 적용: {title} (hwnd: {hwnd})")
            
            # 통합 마우스 가둠 시스템 사용
            integrated_constraint = get_integrated_constraint()
            
            # 자동 복구 및 소리 알림 활성화
            result = integrated_constraint.apply_constraint(
                hwnd=hwnd,
                auto_restore=True,  # 창 활성화 시 자동 복구
                sound_notification=True  # 소리 알림
            )
            
            if result:
                self.constrained_windows.add(hwnd)
                logger.info(f"통합 마우스 가둠 적용 성공: {title}")
                return True
            else:
                logger.error(f"통합 마우스 가둠 적용 실패: {title}")
                return False
                
        except ImportError as e:
            logger.error(f"Required modules not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Mouse constraint error: {e}")
            return False
    
    def release_mouse_constraint(self, hwnd: Optional[int] = None) -> bool:
        """
        마우스 가둠 해제 - 통합 시스템 사용
        """
        try:
            from .integrated_mouse_constraint import get_integrated_constraint
            
            logger.info(f"통합 시스템으로 마우스 가둠 해제: {hwnd if hwnd else 'all'}")
            
            # 통합 마우스 가둠 시스템 사용
            integrated_constraint = get_integrated_constraint()
            result = integrated_constraint.remove_constraint(hwnd)
            
            if result:
                if hwnd:
                    self.constrained_windows.discard(hwnd)
                    logger.info(f"마우스 가둠 해제 성공: {hwnd}")
                else:
                    self.constrained_windows.clear()
                    logger.info("모든 마우스 가둠 해제 성공")
                return True
            else:
                logger.error("마우스 가둠 해제 실패")
                return False
                
        except Exception as e:
            logger.error(f"마우스 가둠 해제 오류: {e}")
            return False
    
    def apply_size_position_lock(self, hwnd: int, lock_config: Dict[str, Any], 
                               enhanced_config: Optional[Dict] = None) -> bool:
        """
        창 크기/위치 고정 - 통합 시스템 사용
        
        Args:
            hwnd: 창 핸들
            lock_config: {
                'lock_size': bool,
                'lock_width': bool, 
                'lock_height': bool,
                'lock_position': bool,
                'target_rect': (x, y, width, height)
            }
        """
        try:
            import win32gui
            from .integrated_window_lock import get_integrated_window_lock
            
            if not win32gui.IsWindow(hwnd):
                logger.error(f"Invalid window handle for size lock: {hwnd}")
                return False
            
            title = win32gui.GetWindowText(hwnd)
            logger.info(f"통합 창 고정 시스템으로 적용: {title} (hwnd: {hwnd})")
            
            # 통합 창 고정 시스템 사용
            integrated_lock = get_integrated_window_lock()
            
            # 자동 복구 활성화 (향상된 설정 포함)
            result = integrated_lock.apply_window_lock(
                hwnd=hwnd,
                lock_config=lock_config,
                auto_restore=True,  # 창 활성화 시 자동 복구
                enhanced_config=enhanced_config  # 향상된 모니터링 설정
            )
            
            if result:
                self.locked_windows[hwnd] = {
                    'target_rect': lock_config.get('target_rect'),
                    'lock_size': lock_config.get('lock_size', True),
                    'lock_width': lock_config.get('lock_width', True),
                    'lock_height': lock_config.get('lock_height', True), 
                    'lock_position': lock_config.get('lock_position', True),
                    'monitoring': True,
                    'restore_attempts': 0,
                    'max_attempts': 100,
                    'integrated': True  # 통합 시스템 사용 표시
                }
                logger.info(f"통합 창 고정 적용 성공: {title}")
                return True
            else:
                logger.error(f"통합 창 고정 적용 실패: {title}")
                return False
                
        except ImportError as e:
            logger.error(f"Required modules not available: {e}")
            return False
        except Exception as e:
            logger.error(f"창 고정 오류: {e}")
            return False
    
    def _monitor_window_lock(self, hwnd: int):
        """창 크기/위치 모니터링 스레드 - 개선된 구현"""
        try:
            import win32gui
            import win32con
            import win32api
            
            config = self.locked_windows.get(hwnd)
            if not config:
                return
            
            target_rect = config['target_rect']
            target_x, target_y = target_rect[0], target_rect[1]
            target_width = target_rect[2] - target_rect[0]
            target_height = target_rect[3] - target_rect[1]
            
            logger.info(f"Monitor thread started for window {hwnd}")
            logger.info(f"Target: x={target_x}, y={target_y}, w={target_width}, h={target_height}")
            
            while (self.running and 
                   config.get('monitoring', False) and 
                   config.get('restore_attempts', 0) < config.get('max_attempts', 50)):
                
                try:
                    # 창이 여전히 존재하는지 확인
                    if not win32gui.IsWindow(hwnd):
                        logger.info(f"Window {hwnd} no longer exists, stopping monitor")
                        break
                    
                    # 현재 창 상태 확인
                    current_rect = win32gui.GetWindowRect(hwnd)
                    current_x, current_y = current_rect[0], current_rect[1]
                    current_width = current_rect[2] - current_rect[0]
                    current_height = current_rect[3] - current_rect[1]
                    
                    # 변경 사항 감지
                    position_changed = (config['lock_position'] and 
                                      (current_x != target_x or current_y != target_y))
                    
                    size_changed = False
                    if config['lock_size'] or config['lock_width'] or config['lock_height']:
                        width_changed = config['lock_width'] and current_width != target_width
                        height_changed = config['lock_height'] and current_height != target_height
                        size_changed = width_changed or height_changed
                    
                    if position_changed or size_changed:
                        logger.info(f"Change detected in window {hwnd}")
                        logger.info(f"  Position changed: {position_changed}")
                        logger.info(f"  Size changed: {size_changed}")
                        logger.info(f"  Current: {current_rect}, Target: {target_rect}")
                        
                        # 복원 시도
                        success = self._restore_window_state(hwnd, target_rect, config)
                        
                        config['restore_attempts'] += 1
                        
                        if success:
                            logger.info(f"Successfully restored window {hwnd}")
                        else:
                            logger.warning(f"Failed to restore window {hwnd} (attempt {config['restore_attempts']})")
                    
                    # 모니터링 간격
                    time.sleep(0.1)  # 100ms 간격
                    
                except Exception as e:
                    logger.error(f"Monitor loop error for window {hwnd}: {e}")
                    time.sleep(1)  # 에러 시 더 긴 대기
            
            # 모니터링 종료
            logger.info(f"Monitoring stopped for window {hwnd}")
            if hwnd in self.locked_windows:
                self.locked_windows[hwnd]['monitoring'] = False
            
        except Exception as e:
            logger.error(f"Monitor thread error for window {hwnd}: {e}")
        
        finally:
            # 스레드 정리
            if hwnd in self.monitoring_threads:
                del self.monitoring_threads[hwnd]
    
    def _restore_window_state(self, hwnd: int, target_rect: Tuple[int, int, int, int], config: Dict) -> bool:
        """창 상태 복원 - 다양한 방법 시도"""
        try:
            import win32gui
            import win32con
            import win32api
            
            x, y, width, height = target_rect[0], target_rect[1], target_rect[2] - target_rect[0], target_rect[3] - target_rect[1]
            
            # 방법 1: 기본 SetWindowPos
            try:
                result = win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOP,
                    x, y, width, height,
                    win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
                )
                
                if result:
                    logger.debug(f"SetWindowPos success for window {hwnd}")
                    return True
                else:
                    error_code = win32api.GetLastError()
                    logger.warning(f"SetWindowPos failed with error {error_code}")
                    
            except Exception as e:
                logger.warning(f"SetWindowPos exception: {e}")
            
            # 방법 2: MoveWindow 시도
            try:
                result = win32gui.MoveWindow(hwnd, x, y, width, height, True)
                if result:
                    logger.debug(f"MoveWindow success for window {hwnd}")
                    return True
                    
            except Exception as e:
                logger.warning(f"MoveWindow exception: {e}")
            
            # 방법 3: ShowWindow로 상태 복원 후 위치 설정
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.05)  # 짧은 대기
                
                result = win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOP,
                    x, y, width, height,
                    win32con.SWP_SHOWWINDOW
                )
                
                if result:
                    logger.debug(f"ShowWindow + SetWindowPos success for window {hwnd}")
                    return True
                    
            except Exception as e:
                logger.warning(f"ShowWindow method exception: {e}")
            
            logger.error(f"All restore methods failed for window {hwnd}")
            return False
            
        except Exception as e:
            logger.error(f"Restore window state error: {e}")
            return False
    
    def remove_size_position_lock(self, hwnd: Optional[int] = None) -> bool:
        """
        창 크기/위치 고정 해제 - 통합 시스템 사용
        """
        try:
            from .integrated_window_lock import get_integrated_window_lock
            
            logger.info(f"통합 시스템으로 창 고정 해제: {hwnd if hwnd else 'all'}")
            
            # 통합 창 고정 시스템 사용
            integrated_lock = get_integrated_window_lock()
            result = integrated_lock.remove_window_lock(hwnd)
            
            if result:
                if hwnd:
                    if hwnd in self.locked_windows:
                        del self.locked_windows[hwnd]
                    logger.info(f"창 고정 해제 성공: {hwnd}")
                else:
                    self.locked_windows.clear()
                    logger.info("모든 창 고정 해제 성공")
                return True
            else:
                logger.error("창 고정 해제 실패")
                return False
                
        except Exception as e:
            logger.error(f"창 고정 해제 오류: {e}")
            return False

    def stop_monitoring(self, hwnd: Optional[int] = None):
        """모니터링 중단"""
        if hwnd:
            # 특정 창의 모니터링 중단
            if hwnd in self.locked_windows:
                config = self.locked_windows[hwnd]
                if config.get('integrated', False):
                    # 통합 시스템 사용 중이면 통합 시스템으로 해제
                    self.remove_size_position_lock(hwnd)
                else:
                    # 기존 방식
                    config['monitoring'] = False
            logger.info(f"Stopped monitoring for window {hwnd}")
        else:
            # 모든 모니터링 중단
            for hwnd, config in list(self.locked_windows.items()):
                if config.get('integrated', False):
                    # 통합 시스템 사용 중이면 통합 시스템으로 해제
                    self.remove_size_position_lock(hwnd)
                else:
                    # 기존 방식
                    config['monitoring'] = False
            self.running = False
            logger.info("Stopped all window monitoring")
    
    def get_status(self) -> Dict:
        """현재 상태 반환"""
        return {
            'constrained_windows': len(self.constrained_windows),
            'locked_windows': len(self.locked_windows),
            'active_threads': len(self.monitoring_threads),
            'locked_windows_detail': {
                hwnd: {
                    'monitoring': config.get('monitoring', False),
                    'restore_attempts': config.get('restore_attempts', 0),
                    'max_attempts': config.get('max_attempts', 50)
                }
                for hwnd, config in self.locked_windows.items()
            }
        }


# 전역 인스턴스
_advanced_features = None

def get_advanced_features() -> AdvancedWindowFeatures:
    """고급 기능 인스턴스 반환 (싱글톤)"""
    global _advanced_features
    if _advanced_features is None:
        _advanced_features = AdvancedWindowFeatures()
    return _advanced_features