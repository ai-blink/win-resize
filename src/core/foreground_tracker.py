"""
Foreground Window Tracker
=========================

오버레이 버튼이 "직전에 활성화되어 있던 창"을 대상으로 프로필을 적용할 수
있도록 foreground 창을 지속 추적한다.

존재 이유:
오버레이 버튼은 WS_EX_NOACTIVATE로 만들어 클릭해도 포커스를 빼앗지 않는다.
그러나 Qt의 내부 활성화 처리나 사용자가 본창을 거쳐 오는 경로 때문에
클릭 시점의 GetForegroundWindow()가 우리 앱 창을 가리킬 수 있다. 그 경우에도
"사용자가 조작하던 창"을 잃지 않으려면 마지막으로 유효했던 대상 창을 따로
보관해야 한다. 이 모듈이 그 역할을 한다.

추적 방식:
200ms QTimer 폴링을 쓴다. SetWinEventHook은 별도 스레드 메시지 루프가 필요하고
enhanced_window_monitor가 이미 다른 용도로 그 경로를 점유하고 있어, 결정적이고
디버깅이 쉬운 폴링을 선택했다. 200ms 주기의 GetForegroundWindow 호출 비용은
무시할 수 있는 수준이다.
"""

import logging
from typing import Any, Dict, Optional, Set

from PyQt5.QtCore import QObject, QTimer

try:
    import win32con
    import win32gui
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)

# 대상이 될 수 없는 셸 및 시스템 창 클래스.
# 바탕화면과 작업표시줄이 잠시 foreground가 되어도 대상을 덮어쓰지 않는다.
SHELL_WINDOW_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "NotifyIconOverflowWindow",
    "Windows.UI.Core.CoreWindow",
    "TaskListThumbnailWnd",
    "ForegroundStaging",
}

DEFAULT_POLL_INTERVAL_MS = 200


class ForegroundTracker(QObject):
    """마지막으로 활성화되었던 대상 창을 추적한다."""

    def __init__(self, poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS, parent=None):
        super().__init__(parent)
        self._excluded_hwnds: Set[int] = set()
        self._target_hwnd: Optional[int] = None
        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval_ms)
        self._timer.timeout.connect(self._poll)

    # -- 수명 주기 -----------------------------------------------------

    def start(self):
        """폴링을 시작한다."""
        if not WIN32_AVAILABLE:
            logger.error("win32 모듈을 사용할 수 없어 foreground 추적을 시작하지 못했습니다")
            return
        if not self._timer.isActive():
            self._poll()  # 시작 직후부터 대상이 있도록 한 번 즉시 읽는다
            self._timer.start()
            logger.info("Foreground 추적 시작 (%dms 주기)", self._timer.interval())

    def stop(self):
        """폴링을 중단한다."""
        if self._timer.isActive():
            self._timer.stop()
            logger.info("Foreground 추적 중단")

    # -- 제외 목록 -----------------------------------------------------

    def exclude_hwnd(self, hwnd: int):
        """우리 앱 창처럼 대상이 되면 안 되는 hwnd를 제외 목록에 넣는다."""
        if hwnd:
            self._excluded_hwnds.add(int(hwnd))

    def unexclude_hwnd(self, hwnd: int):
        """제외 목록에서 hwnd를 제거한다."""
        self._excluded_hwnds.discard(int(hwnd))

    def is_excluded(self, hwnd: int) -> bool:
        return int(hwnd) in self._excluded_hwnds

    # -- 조회 ---------------------------------------------------------

    def get_target_hwnd(self) -> Optional[int]:
        """대상 창 핸들을 돌려준다.

        현재 foreground가 유효하면 그것을, 아니면 마지막으로 유효했던 창을
        돌려준다. 이미 닫힌 창이면 None이다.
        """
        if not WIN32_AVAILABLE:
            return None

        current = self._read_foreground()
        if current is not None:
            self._target_hwnd = current

        if self._target_hwnd is None:
            return None

        try:
            if not win32gui.IsWindow(self._target_hwnd):
                logger.info("추적 대상 창이 이미 닫혔습니다: %s", self._target_hwnd)
                self._target_hwnd = None
                return None
        except Exception as exc:
            logger.warning("대상 창 핸들 검증 실패: %s", exc)
            return None

        return self._target_hwnd

    def get_target_window_info(self) -> Optional[Dict[str, Any]]:
        """프로필 적용에 바로 넘길 수 있는 window_info 딕셔너리를 만든다.

        apply_to_window는 hwnd만 필수로 쓰고 나머지 필드는 로깅과 매칭용이다.
        프로세스 정보는 얻지 못해도 적용을 막지 않는다.
        """
        hwnd = self.get_target_hwnd()
        if hwnd is None:
            return None
        return build_window_info(hwnd)

    # -- 내부 ---------------------------------------------------------

    def _poll(self):
        current = self._read_foreground()
        if current is not None and current != self._target_hwnd:
            self._target_hwnd = current
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("추적 대상 변경: %s (%s)", current, _safe_title(current))

    def _read_foreground(self) -> Optional[int]:
        """지금 foreground가 대상으로 삼을 만한 창이면 그 hwnd를 돌려준다."""
        try:
            hwnd = win32gui.GetForegroundWindow()
        except Exception as exc:
            logger.warning("GetForegroundWindow 실패: %s", exc)
            return None

        if not hwnd or not self._is_trackable(hwnd):
            return None
        return hwnd

    def _is_trackable(self, hwnd: int) -> bool:
        if int(hwnd) in self._excluded_hwnds:
            return False

        try:
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return False
            if win32gui.GetWindowText(hwnd) == "" and win32gui.GetClassName(hwnd) in SHELL_WINDOW_CLASSES:
                return False
            if win32gui.GetClassName(hwnd) in SHELL_WINDOW_CLASSES:
                return False
        except Exception:
            return False

        return True


def build_window_info(hwnd: int) -> Dict[str, Any]:
    """hwnd 하나로 profile_manager가 받는 형식의 딕셔너리를 만든다."""
    info: Dict[str, Any] = {
        'hwnd': hwnd,
        'title': '',
        'class_name': '',
        'process_name': '',
        'executable_path': '',
        'rect': (0, 0, 0, 0),
        'is_maximized': False,
        'is_minimized': False,
        'is_visible': True,
    }

    if not WIN32_AVAILABLE:
        return info

    try:
        info['title'] = win32gui.GetWindowText(hwnd)
        info['class_name'] = win32gui.GetClassName(hwnd)
        info['rect'] = win32gui.GetWindowRect(hwnd)
        info['is_visible'] = bool(win32gui.IsWindowVisible(hwnd))
        info['is_minimized'] = bool(win32gui.IsIconic(hwnd))

        placement = win32gui.GetWindowPlacement(hwnd)
        info['is_maximized'] = placement[1] == win32con.SW_SHOWMAXIMIZED
    except Exception as exc:
        logger.warning("창 기본 정보 수집 실패 (hwnd=%s): %s", hwnd, exc)

    if PSUTIL_AVAILABLE:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid:
                process = psutil.Process(pid)
                info['process_name'] = process.name()
                info['executable_path'] = process.exe()
        except Exception as exc:
            # 권한이 높은 프로세스는 경로를 못 읽는다. 적용 자체는 막지 않는다.
            logger.debug("프로세스 정보 수집 실패 (hwnd=%s): %s", hwnd, exc)

    return info


def _safe_title(hwnd: int) -> str:
    try:
        return win32gui.GetWindowText(hwnd)
    except Exception:
        return "?"
