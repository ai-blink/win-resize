using System.Runtime.InteropServices;
using System.Text;
using WindowResizer.Core.Profiles;
using WindowResizer.Core.Windowing;
using static WindowResizer.Infrastructure.Windowing.NativeMethods;

namespace WindowResizer.Infrastructure.Windowing;

/// <summary>열거된 최상위 창 하나.</summary>
public sealed record DesktopWindow(nint Handle, WindowInfo Info, uint ProcessId, PixelRect Rect, bool IsMaximized, bool IsMinimized);

/// <summary>모니터 하나. 좌표는 물리 픽셀, 가상 데스크톱 기준.</summary>
public sealed record MonitorArea(string DeviceName, PixelRect Bounds, PixelRect WorkArea, bool IsPrimary);

/// <summary>
/// <see cref="IWindowOperations"/> 의 Win32 구현.
///
/// 모든 호출은 스레드 DPI 컨텍스트를 per-monitor v2 로 바꾼 채 한다. 그래야 어떤 호스트
/// (DPI 를 모르는 테스트 호스트 포함)에서 불려도 좌표가 물리 픽셀이다. 인식하지 않는 스레드는
/// 배율이 걸린 모니터에서 가상화된 좌표를 받는다 - 저장된 프로필과 단위가 어긋난다.
/// </summary>
public sealed class Win32Windows : IWindowOperations
{
    public bool IsWindow(nint window) => NativeMethods.IsWindow(window);

    public bool IsMaximized(nint window) => IsZoomed(window);

    public bool IsMinimized(nint window) => IsIconic(window);

    public PixelRect? GetRect(nint window)
    {
        using var _ = new DpiScope();
        return GetWindowRect(window, out var r) ? ToRect(r) : null;
    }

    /// <summary>
    /// <c>rcNormalPosition</c> 은 도구 창이 아니면 <b>작업 영역 좌표</b>다 - 작업 표시줄이 왼쪽/위에
    /// 있으면 화면 좌표와 그만큼 어긋난다. 창이 속한 모니터의 작업 영역 오프셋을 더해 화면 좌표로 바꾼다.
    /// 최소화된 창도 <c>MonitorFromWindow</c> 는 최소화 전 위치의 모니터를 돌려준다.
    /// </summary>
    public WindowPlacement? GetPlacement(nint window)
    {
        using var _ = new DpiScope();
        var p = new WINDOWPLACEMENT { length = Marshal.SizeOf<WINDOWPLACEMENT>() };
        if (!GetWindowPlacement(window, ref p)) return null;

        var normal = ToRect(p.rcNormalPosition);
        if ((GetWindowLongPtr(window, GWL_EXSTYLE) & WS_EX_TOOLWINDOW) == 0)
        {
            var info = new MONITORINFOEX { cbSize = Marshal.SizeOf<MONITORINFOEX>(), szDevice = "" };
            var monitor = MonitorFromWindow(window, MONITOR_DEFAULTTONEAREST);
            if (monitor != 0 && GetMonitorInfoW(monitor, ref info))
            {
                normal = normal with
                {
                    X = normal.X + info.rcWork.Left - info.rcMonitor.Left,
                    Y = normal.Y + info.rcWork.Top - info.rcMonitor.Top,
                };
            }
        }
        return new WindowPlacement(normal, (p.flags & WPF_RESTORETOMAXIMIZED) != 0);
    }

    public bool Restore(nint window)
    {
        using var _ = new DpiScope();
        ShowWindow(window, SW_RESTORE);
        return !IsZoomed(window) && !IsIconic(window);
    }

    public bool Maximize(nint window)
    {
        using var _ = new DpiScope();
        ShowWindow(window, SW_SHOWMAXIMIZED);
        return IsZoomed(window);
    }

    public bool Minimize(nint window)
    {
        using var _ = new DpiScope();
        ShowWindow(window, SW_MINIMIZE);
        return IsIconic(window);
    }

    /// <summary>
    /// <c>MoveWindow</c> 의 BOOL 은 진짜 성공 여부다(<c>ShowWindow</c> 와 다르다).
    /// 창이 최소 크기를 강제하면 요청과 결과가 다를 수 있으므로 여기서는 사각형 일치를 요구하지 않는다.
    /// 일치 여부는 호출자가 <see cref="GetRect"/> 로 확인한다.
    /// </summary>
    public bool Move(nint window, PixelRect rect)
    {
        using var _ = new DpiScope();
        return MoveWindow(window, rect.X, rect.Y, rect.Width, rect.Height, true);
    }

    public bool SetTopmost(nint window, bool topmost)
    {
        using var _ = new DpiScope();
        SetWindowPos(window, topmost ? HWND_TOPMOST : HWND_NOTOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
        var isTopmost = (GetWindowLongPtr(window, GWL_EXSTYLE) & WS_EX_TOPMOST) != 0;
        return isTopmost == topmost;
    }

    /// <summary>보이고 제목이 있는 최상위 창. 목록에 무엇을 숨길지는 이 계층의 결정이 아니다.</summary>
    public IReadOnlyList<DesktopWindow> EnumerateWindows()
    {
        using var _ = new DpiScope();
        var handles = new List<nint>();
        EnumWindows((hwnd, _) =>
        {
            if (IsWindowVisible(hwnd) && GetWindowTextLengthW(hwnd) > 0) handles.Add(hwnd);
            return true;
        }, 0);

        var result = new List<DesktopWindow>(handles.Count);
        foreach (var hwnd in handles)
        {
            if (!GetWindowRect(hwnd, out var r)) continue;
            GetWindowThreadProcessId(hwnd, out var pid);
            var exePath = GetExecutablePath(pid);
            var info = new WindowInfo(
                Title: GetTitle(hwnd),
                ProcessName: exePath.Length > 0 ? Path.GetFileName(exePath) : "",
                ClassName: GetClassName(hwnd),
                ExecutablePath: exePath);
            result.Add(new DesktopWindow(hwnd, info, pid, ToRect(r), IsZoomed(hwnd), IsIconic(hwnd)));
        }
        return result;
    }

    /// <summary>창 목록에 보여 줄 창. 규칙은 PyQt5 USER_WINDOWS 필터(<see cref="WindowListFilter"/>).</summary>
    public IReadOnlyList<DesktopWindow> EnumerateUserWindows() =>
        EnumerateWindows().Where(w => WindowListFilter.IsUserWindow(w.Info, w.Rect)).ToList();

    public IReadOnlyList<MonitorArea> EnumerateMonitors()
    {
        using var _ = new DpiScope();
        var monitors = new List<MonitorArea>();
        EnumDisplayMonitors(0, 0, (nint monitor, nint _, ref RECT _, nint _) =>
        {
            var info = new MONITORINFOEX { cbSize = Marshal.SizeOf<MONITORINFOEX>(), szDevice = "" };
            if (GetMonitorInfoW(monitor, ref info))
            {
                monitors.Add(new MonitorArea(
                    info.szDevice, ToRect(info.rcMonitor), ToRect(info.rcWork),
                    (info.dwFlags & MONITORINFOF_PRIMARY) != 0));
            }
            return true;
        }, 0);
        return monitors;
    }

    /// <summary>
    /// 실행 파일 전체 경로. 권한이 부족하면(상승된 프로세스 등) 빈 문자열이다 -
    /// 그 창은 경로 매칭이 불일치가 된다. PyQt5 도 같다.
    /// </summary>
    public static string GetExecutablePath(uint processId)
    {
        var process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, processId);
        if (process == 0) return "";
        try
        {
            var buffer = new StringBuilder(1024);
            var size = buffer.Capacity;
            return QueryFullProcessImageNameW(process, 0, buffer, ref size) ? buffer.ToString(0, size) : "";
        }
        finally
        {
            CloseHandle(process);
        }
    }

    /// <summary>창에 닫기를 요청한다. 응답은 기다리지 않는다.</summary>
    public static bool RequestClose(nint window) => PostMessageW(window, WM_CLOSE, 0, 0);

    private static string GetTitle(nint hwnd)
    {
        var length = GetWindowTextLengthW(hwnd);
        var buffer = new StringBuilder(length + 1);
        GetWindowTextW(hwnd, buffer, buffer.Capacity);
        return buffer.ToString();
    }

    /// <summary>창 하나의 매칭 정보. 오버레이가 직전 창의 제목과 경로를 알려 줄 때 쓴다.</summary>
    public static WindowInfo DescribeWindow(nint hwnd)
    {
        GetWindowThreadProcessId(hwnd, out var pid);
        var exePath = GetExecutablePath(pid);
        return new WindowInfo(GetTitle(hwnd), exePath.Length > 0 ? Path.GetFileName(exePath) : "", GetClassName(hwnd), exePath);
    }

    public static string GetClassNameOf(nint hwnd) => GetClassName(hwnd);

    private static string GetClassName(nint hwnd)
    {
        var buffer = new StringBuilder(256);
        GetClassNameW(hwnd, buffer, buffer.Capacity);
        return buffer.ToString();
    }

    private static PixelRect ToRect(RECT r) => new(r.Left, r.Top, r.Right - r.Left, r.Bottom - r.Top);
}

/// <summary>스레드 DPI 인식을 잠시 per-monitor v2 로 바꾸고 원래대로 돌린다.</summary>
internal readonly struct DpiScope : IDisposable
{
    private readonly nint _previous;

    public DpiScope() => _previous = SetThreadDpiAwarenessContext(DpiAwarenessPerMonitorV2);

    public void Dispose()
    {
        if (_previous != 0) SetThreadDpiAwarenessContext(_previous);
    }
}
