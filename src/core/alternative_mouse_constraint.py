#!/usr/bin/env python3
"""
Alternative Mouse Constraint System
====================================

ClipCursor가 None을 반환하거나 실패할 때 사용하는 대안적인 마우스 제약 시스템
저수준 마우스 훅을 이용한 직접적인 마우스 제어 구현
"""

import logging
import time
import threading
from typing import Optional, Tuple, Dict, Any, Callable
from ctypes import wintypes
import ctypes
from ctypes import windll, POINTER, c_int, c_void_p, Structure, byref
import win32gui
import win32con
import win32api

logger = logging.getLogger(__name__)

# Try to import pyhook3 for more reliable mouse hooking
try:
    import pyWinhook as pyHook
    PYHOOK_AVAILABLE = True
    logger.info("PyWinhook available - using for mouse hooking")
except ImportError:
    try:
        import pyhook3 as pyHook
        PYHOOK_AVAILABLE = True
        logger.info("PyHook3 available - using for mouse hooking")
    except ImportError:
        PYHOOK_AVAILABLE = False
        logger.warning("Neither PyWinhook nor PyHook3 available - using ctypes hook")

# Windows API 상수들
WH_MOUSE_LL = 14
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A

class POINT(Structure):
    _fields_ = [("x", c_int), ("y", c_int)]

class MSLLHOOKSTRUCT(Structure):
    _fields_ = [("x", c_int),
                ("y", c_int),
                ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", POINTER(wintypes.ULONG))]

# 훅 프로시저 타입 정의
HOOKPROC = ctypes.WINFUNCTYPE(c_int, c_int, wintypes.WPARAM, wintypes.LPARAM)

class AlternativeMouseConstraint:
    """대안적인 마우스 제약 시스템"""
    
    def __init__(self):
        self.hook = None
        self.constraint_rect = None
        self.constrained_window = None
        self.is_active = False
        self.escape_key_pressed = False
        self.pyhook_manager = None
        
        # 통계
        self.blocked_moves = 0
        self.total_moves = 0
        
        # 폴링 기반 제약을 위한 스레드
        self.polling_thread = None
        self.stop_polling = False
        
        logger.info(f"Alternative mouse constraint system initialized (PyHook available: {PYHOOK_AVAILABLE})")
    
    def apply_constraint(self, hwnd: int, rect: Optional[Tuple[int, int, int, int]] = None) -> bool:
        """
        대안적인 마우스 제약 적용
        
        Args:
            hwnd: 창 핸들
            rect: 제약 영역 (None이면 창 영역 사용)
        
        Returns:
            bool: 성공 여부
        """
        try:
            if not win32gui.IsWindow(hwnd):
                logger.error(f"Invalid window handle: {hwnd}")
                return False
            
            # 제약 영역 결정
            if rect is None:
                rect = win32gui.GetWindowRect(hwnd)
            
            # 비정상적인 좌표 확인
            if rect[0] <= -30000 or rect[1] <= -30000:
                logger.warning("Window appears minimized, attempting to restore...")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)
                rect = win32gui.GetWindowRect(hwnd)
                
                if rect[0] <= -30000 or rect[1] <= -30000:
                    logger.error(f"Cannot get valid window rect: {rect}")
                    return False
            
            title = win32gui.GetWindowText(hwnd)
            logger.info(f"Applying alternative mouse constraint to: {title}")
            logger.info(f"Constraint rect: {rect}")
            
            # 이전 제약 해제
            if self.is_active:
                self.release_constraint()
                time.sleep(0.1)
            
            # 새로운 제약 설정
            self.constraint_rect = rect
            self.constrained_window = hwnd
            
            # 폴링 기반 제약만 사용 (가장 안정적이고 자연스러움)
            logger.info("Using polling-based mouse constraint (most reliable and smooth)...")
            success = self._install_polling_constraint()
            
            if success:
                self.is_active = True
                logger.info("Alternative mouse constraint applied successfully")
                
                # 현재 마우스가 영역 밖에 있으면 안쪽으로 이동
                self._ensure_mouse_in_bounds()
                
                return True
            else:
                logger.error("All mouse constraint methods failed")
                return False
                
        except Exception as e:
            logger.error(f"Error applying alternative mouse constraint: {e}")
            return False
    
    def release_constraint(self) -> bool:
        """마우스 제약 해제"""
        try:
            logger.info("Releasing alternative mouse constraint...")
            
            # PyHook 해제
            if self.pyhook_manager:
                try:
                    self.pyhook_manager.UnhookMouse()
                    self.pyhook_manager = None
                    logger.info("PyHook mouse constraint released")
                except:
                    pass
            
            # 저수준 훅 해제
            if self.hook:
                try:
                    windll.user32.UnhookWindowsHookEx(self.hook)
                    self.hook = None
                    logger.info("Low-level mouse hook released")
                except:
                    pass
            
            # 폴링 스레드 중지
            if self.polling_thread and self.polling_thread.is_alive():
                self.stop_polling = True
                self.polling_thread.join(timeout=1.0)
                logger.info("Polling thread stopped")
            
            # 상태 초기화
            self.is_active = False
            self.constraint_rect = None
            self.constrained_window = None
            self.escape_key_pressed = False
            self.stop_polling = False
            
            logger.info(f"Mouse constraint released. Stats - Blocked: {self.blocked_moves}, Total: {self.total_moves}")
            
            # 통계 초기화
            self.blocked_moves = 0
            self.total_moves = 0
            
            return True
                
        except Exception as e:
            logger.error(f"Error releasing mouse constraint: {e}")
            return False
    
    def _install_mouse_hook(self) -> bool:
        """저수준 마우스 훅 설치"""
        try:
            # 훅 프로시저 등록 - GLOBAL로 유지해야 함
            self.hook_proc = HOOKPROC(self._low_level_mouse_proc)
            
            # GetModuleHandle로 현재 모듈 핸들 가져오기
            kernel32 = windll.kernel32
            kernel32.GetModuleHandleW.restype = wintypes.HMODULE
            kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            
            # 현재 프로세스 모듈 핸들
            hmod = kernel32.GetModuleHandleW(None)
            
            # 훅 설치 - A버전 사용 (더 안정적)
            user32 = windll.user32
            user32.SetWindowsHookExA.argtypes = [
                ctypes.c_int,
                HOOKPROC,
                wintypes.HINSTANCE,
                wintypes.DWORD
            ]
            user32.SetWindowsHookExA.restype = wintypes.HHOOK
            
            logger.info(f"Installing low-level mouse hook...")
            logger.info(f"Hook type: WH_MOUSE_LL ({WH_MOUSE_LL})")
            logger.info(f"Module handle: {hmod}")
            
            self.hook = user32.SetWindowsHookExA(
                WH_MOUSE_LL,
                self.hook_proc,
                ctypes.cast(hmod, wintypes.HINSTANCE),
                0  # 전역 훅 (모든 스레드)
            )
            
            if self.hook:
                logger.info(f"SUCCESS: Mouse hook installed successfully: {self.hook}")
                
                # 즉시 테스트
                logger.info("Testing hook responsiveness...")
                return True
            else:
                error_code = windll.kernel32.GetLastError()
                logger.error(f"FAILED: Hook installation failed, error: {error_code}")
                return False
                
        except Exception as e:
            logger.error(f"EXCEPTION: Error installing mouse hook: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _install_pyhook_constraint(self) -> bool:
        """PyHook을 사용한 마우스 제약 설치"""
        try:
            if not PYHOOK_AVAILABLE:
                return False
            
            # PyHook 매니저 생성
            self.pyhook_manager = pyHook.HookManager()
            
            # 마우스 이동 이벤트 핸들러
            def on_mouse_move(event):
                try:
                    self.total_moves += 1
                    
                    if not self.is_active or not self.constraint_rect:
                        return True
                    
                    mouse_x, mouse_y = event.Position
                    rect = self.constraint_rect
                    
                    # 영역 내부에 있으면 통과
                    if rect[0] <= mouse_x <= rect[2] and rect[1] <= mouse_y <= rect[3]:
                        return True
                    
                    # 영역 밖으로 나가려 하면 차단
                    self.blocked_moves += 1
                    logger.info(f"PyHook BLOCKING mouse move: ({mouse_x}, {mouse_y})")
                    
                    # 경계로 마우스 위치 조정
                    constrained_x = max(rect[0], min(mouse_x, rect[2]))
                    constrained_y = max(rect[1], min(mouse_y, rect[3]))
                    
                    # 마우스를 제약 영역 내로 즉시 이동
                    win32api.SetCursorPos((constrained_x, constrained_y))
                    
                    # 이벤트 차단
                    return False
                    
                except Exception as e:
                    logger.error(f"Error in PyHook mouse handler: {e}")
                    return True
            
            # 마우스 훅 등록
            self.pyhook_manager.MouseMove = on_mouse_move
            self.pyhook_manager.HookMouse()
            
            logger.info("PyHook mouse constraint installed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error installing PyHook constraint: {e}")
            return False
    
    def _install_polling_constraint(self) -> bool:
        """폴링 기반 마우스 제약 설치"""
        try:
            logger.info("Installing polling-based mouse constraint...")
            
            def polling_worker():
                """폴링 워커 스레드"""
                last_pos = win32gui.GetCursorPos()
                
                while not self.stop_polling and self.is_active:
                    try:
                        current_pos = win32gui.GetCursorPos()
                        
                        if current_pos != last_pos:
                            self.total_moves += 1
                            
                            if self.constraint_rect:
                                rect = self.constraint_rect
                                mouse_x, mouse_y = current_pos
                                
                                # 영역 밖에 있으면 안쪽으로 이동
                                if not (rect[0] <= mouse_x <= rect[2] and rect[1] <= mouse_y <= rect[3]):
                                    self.blocked_moves += 1
                                    logger.info(f"Polling CONSTRAINING mouse: {current_pos}")
                                    
                                    # 경계로 마우스 위치 조정
                                    constrained_x = max(rect[0], min(mouse_x, rect[2]))
                                    constrained_y = max(rect[1], min(mouse_y, rect[3]))
                                    
                                    win32api.SetCursorPos((constrained_x, constrained_y))
                            
                            last_pos = current_pos
                        
                        time.sleep(0.001)  # 1ms 간격으로 폴링 (더 자연스러운 움직임)
                        
                    except Exception as e:
                        logger.error(f"Error in polling worker: {e}")
                        break
                
                logger.info("Polling worker thread ended")
            
            # 폴링 스레드 시작
            self.polling_thread = threading.Thread(target=polling_worker, daemon=True)
            self.polling_thread.start()
            
            logger.info("Polling-based mouse constraint installed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error installing polling constraint: {e}")
            return False
    
    def _low_level_mouse_proc(self, nCode: int, wParam: wintypes.WPARAM, lParam: wintypes.LPARAM) -> int:
        """저수준 마우스 훅 프로시저"""
        try:
            # 디버그: 훅이 호출되는지 확인
            if self.total_moves % 50 == 0:  # 50번마다 한 번 로그
                logger.info(f"Hook called: nCode={nCode}, wParam={wParam}, total_moves={self.total_moves}")
            
            # 정상적인 메시지가 아니면 통과
            if nCode < 0:
                return windll.user32.CallNextHookEx(None, nCode, wParam, lParam)
            
            # 제약이 비활성이면 통과
            if not self.is_active or not self.constraint_rect:
                if self.total_moves % 100 == 0:  # 100번마다 한 번 로그
                    logger.info(f"Hook inactive or no constraint: active={self.is_active}, rect={self.constraint_rect}")
                return windll.user32.CallNextHookEx(None, nCode, wParam, lParam)
            
            # 마우스 이동 메시지 처리
            if wParam == WM_MOUSEMOVE:
                self.total_moves += 1
                
                # 마우스 데이터 파싱
                mouse_data = ctypes.cast(lParam, POINTER(MSLLHOOKSTRUCT)).contents
                mouse_x, mouse_y = mouse_data.x, mouse_data.y
                
                # 디버그 로그 (처음 10번만)
                if self.total_moves <= 10:
                    logger.info(f"Mouse move #{self.total_moves}: ({mouse_x}, {mouse_y})")
                
                # 제약 영역 확인
                rect = self.constraint_rect
                
                # 영역 내부에 있으면 통과
                if rect[0] <= mouse_x <= rect[2] and rect[1] <= mouse_y <= rect[3]:
                    return windll.user32.CallNextHookEx(None, nCode, wParam, lParam)
                
                # 영역 밖으로 나가려 하면 차단
                self.blocked_moves += 1
                logger.info(f"BLOCKING mouse move #{self.blocked_moves}: ({mouse_x}, {mouse_y}) -> constraint area {rect}")
                
                # 경계로 마우스 위치 조정
                constrained_x = max(rect[0], min(mouse_x, rect[2]))
                constrained_y = max(rect[1], min(mouse_y, rect[3]))
                
                logger.info(f"Constraining mouse to: ({constrained_x}, {constrained_y})")
                
                # 마우스를 제약 영역 내로 즉시 이동
                win32api.SetCursorPos((constrained_x, constrained_y))
                
                # 이벤트 차단 (1 반환)
                return 1
            
            # 다른 마우스 이벤트는 통과
            return windll.user32.CallNextHookEx(None, nCode, wParam, lParam)
            
        except Exception as e:
            logger.error(f"CRITICAL ERROR in mouse hook procedure: {e}")
            import traceback
            traceback.print_exc()
            # 오류 시에는 이벤트 통과
            return windll.user32.CallNextHookEx(None, nCode, wParam, lParam)
    
    def _ensure_mouse_in_bounds(self):
        """마우스가 제약 영역 내에 있도록 보장"""
        try:
            if not self.constraint_rect:
                return
            
            current_pos = win32gui.GetCursorPos()
            rect = self.constraint_rect
            
            # 현재 위치가 영역 내에 있으면 OK
            if rect[0] <= current_pos[0] <= rect[2] and rect[1] <= current_pos[1] <= rect[3]:
                logger.info(f"Mouse already in bounds: {current_pos}")
                return
            
            # 영역 내로 이동
            constrained_x = max(rect[0], min(current_pos[0], rect[2]))
            constrained_y = max(rect[1], min(current_pos[1], rect[3]))
            
            win32api.SetCursorPos((constrained_x, constrained_y))
            logger.info(f"Moved mouse from {current_pos} to ({constrained_x}, {constrained_y})")
            
        except Exception as e:
            logger.error(f"Error ensuring mouse in bounds: {e}")
    
    def is_constraint_active(self) -> bool:
        """제약이 활성 상태인지 확인"""
        return self.is_active and self.hook is not None
    
    def get_constraint_info(self) -> Dict[str, Any]:
        """현재 제약 정보 반환"""
        return {
            'active': self.is_active,
            'window': self.constrained_window,
            'rect': self.constraint_rect,
            'hook_handle': self.hook,
            'blocked_moves': self.blocked_moves,
            'total_moves': self.total_moves,
            'block_rate': (self.blocked_moves / self.total_moves * 100) if self.total_moves > 0 else 0
        }
    
    def test_constraint(self, hwnd: int, duration: int = 5) -> Dict[str, Any]:
        """
        제약 테스트 (지정된 시간 동안)
        
        Args:
            hwnd: 테스트할 창 핸들
            duration: 테스트 시간 (초)
        
        Returns:
            Dict: 테스트 결과
        """
        try:
            logger.info(f"Starting {duration}s constraint test...")
            
            # 제약 적용
            if not self.apply_constraint(hwnd):
                return {'success': False, 'error': 'Failed to apply constraint'}
            
            # 테스트 시간 대기
            time.sleep(duration)
            
            # 결과 수집
            result = self.get_constraint_info()
            
            # 제약 해제
            self.release_constraint()
            
            result['success'] = True
            result['test_duration'] = duration
            
            logger.info(f"Constraint test completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in constraint test: {e}")
            self.release_constraint()  # 안전하게 해제
            return {'success': False, 'error': str(e)}

# 전역 대안 제약 시스템 인스턴스
_alternative_constraint = None

def get_alternative_constraint() -> AlternativeMouseConstraint:
    """대안 마우스 제약 시스템 싱글톤 인스턴스"""
    global _alternative_constraint
    if _alternative_constraint is None:
        _alternative_constraint = AlternativeMouseConstraint()
    return _alternative_constraint

def test_alternative_constraint():
    """대안 제약 시스템 테스트"""
    print("=== Alternative Mouse Constraint Test ===")
    
    try:
        # 스타크래프트 창 찾기
        def enum_windows_proc(hwnd, windows):
            title = win32gui.GetWindowText(hwnd)
            if title and ("Brood War" in title or "StarCraft" in title):
                if win32gui.IsWindowVisible(hwnd):
                    windows.append((hwnd, title))
            return True
        
        windows = []
        win32gui.EnumWindows(enum_windows_proc, windows)
        
        if not windows:
            print("스타크래프트 창을 찾을 수 없습니다!")
            return False
        
        hwnd, title = windows[0]
        print(f"테스트 대상: {title}")
        
        # 대안 제약 시스템 테스트
        alt_constraint = get_alternative_constraint()
        result = alt_constraint.test_constraint(hwnd, 5)
        
        print(f"테스트 결과: {result}")
        
        if result['success']:
            print("SUCCESS: 대안적인 마우스 제약 시스템이 작동합니다!")
            print(f"SUCCESS: 총 {result['total_moves']}번의 마우스 이동 중 {result['blocked_moves']}번 차단")
            print(f"SUCCESS: 차단율: {result['block_rate']:.1f}%")
            return True
        else:
            print(f"FAILED: 테스트 실패: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"테스트 오류: {e}")
        return False

if __name__ == "__main__":
    test_alternative_constraint()