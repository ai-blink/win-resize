using WindowResizer.Core.Windowing;
using static WindowResizer.Infrastructure.Windowing.NativeMethods;

namespace WindowResizer.Infrastructure.Windowing;

/// <summary>
/// 오버레이 버튼이 프로필을 적용할 "직전에 쓰던 창"을 기억한다(PyQt5 <c>ForegroundTracker</c>).
///
/// PyQt5 는 200ms 폴링이었다. 여기서는 <see cref="WindowEventWatcher.ForegroundChanged"/> 를 쓴다 - 폴링이 없고,
/// 감시기가 이 프로세스의 창을 이미 거르므로 PyQt5 처럼 본창과 버튼을 하나씩 제외 목록에 넣을 필요가 없다.
/// 셸 창(바탕화면, 작업 표시줄)은 <see cref="ForegroundRules"/> 가 거른다.
///
/// 이벤트는 감시기 스레드에서 오고 <see cref="Target"/> 은 UI 스레드가 읽는다. 값 하나라 Volatile 로 충분하다.
/// </summary>
public sealed class ForegroundTracker : IDisposable
{
    private readonly WindowEventWatcher _watcher;
    private readonly uint _ownProcessId = (uint)Environment.ProcessId;
    private long _target;

    public ForegroundTracker(WindowEventWatcher watcher)
    {
        _watcher = watcher;
        _watcher.ForegroundChanged += Observe;
        // 시작 직후에도 대상이 있게 지금 전경을 한 번 읽는다.
        Observe(GetForegroundWindow());
    }

    /// <summary>대상 창. 닫혔거나 없으면 null.</summary>
    public nint? Target
    {
        get
        {
            // 클릭 순간의 전경이 쓸 만하면 그것이 가장 최신이다(PyQt5 get_target_hwnd 와 같다).
            Observe(GetForegroundWindow());
            var hwnd = (nint)Volatile.Read(ref _target);
            if (hwnd == 0) return null;
            if (!NativeMethods.IsWindow(hwnd))
            {
                Interlocked.CompareExchange(ref _target, 0, hwnd);
                return null;
            }
            return hwnd;
        }
    }

    private void Observe(nint hwnd)
    {
        if (hwnd == 0) return;
        GetWindowThreadProcessId(hwnd, out var pid);
        if (pid == _ownProcessId) return;
        if (!ForegroundRules.IsTrackable(Win32Windows.GetClassNameOf(hwnd), IsWindowVisible(hwnd))) return;
        Volatile.Write(ref _target, hwnd);
    }

    public void Dispose() => _watcher.ForegroundChanged -= Observe;
}
