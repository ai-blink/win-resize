using static WindowResizer.Infrastructure.Windowing.NativeMethods;

namespace WindowResizer.Infrastructure.Windowing;

/// <summary>
/// 창 이벤트 감시: 전경 창 바뀜, 창 위치/크기 바뀜.
///
/// PyQt5 는 <c>SetWinEventHookW(EVENT_OBJECT_LOCATIONCHANGE, EVENT_SYSTEM_FOREGROUND, ...)</c> 로 걸었는데
/// 최소(0x800B)가 최대(0x0003)보다 커서 범위가 뒤집혀 있다(<c>enhanced_window_monitor.py:132</c>).
/// 그 결함은 옮기지 않는다 - 이벤트마다 범위가 하나인 훅을 따로 건다.
///
/// 커서, 캐럿 같은 자식 객체 이벤트는 거르고 창 자체(<c>OBJID_WINDOW</c>, <c>CHILDID_SELF</c>)만 알린다.
/// 이 프로세스 자신의 창은 알리지 않는다(<c>WINEVENT_SKIPOWNPROCESS</c>).
/// 이벤트는 전용 메시지 스레드에서 불린다.
/// </summary>
public sealed class WindowEventWatcher : IDisposable
{
    private readonly MessageThread _thread;
    private readonly WinEventProc _callback;   // 네이티브가 부르는 동안 GC 되지 않게 붙잡는다
    private readonly List<nint> _hooks = new();

    public WindowEventWatcher()
    {
        _callback = OnWinEvent;
        _thread = new MessageThread("WindowResizer.WindowEvents");
        _thread.Invoke(() =>
        {
            foreach (var eventType in new[] { EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_LOCATIONCHANGE })
            {
                var hook = SetWinEventHook(eventType, eventType, 0, _callback, 0, 0,
                    WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS);
                if (hook == 0) throw new InvalidOperationException($"SetWinEventHook 실패: 0x{eventType:X}");
                _hooks.Add(hook);
            }
            return 0;
        });
    }

    public event Action<nint>? ForegroundChanged;
    public event Action<nint>? LocationChanged;

    private void OnWinEvent(nint hook, uint eventType, nint hwnd, int idObject, int idChild, uint thread, uint time)
    {
        if (hwnd == 0 || idObject != OBJID_WINDOW || idChild != CHILDID_SELF) return;

        if (eventType == EVENT_SYSTEM_FOREGROUND) ForegroundChanged?.Invoke(hwnd);
        else if (eventType == EVENT_OBJECT_LOCATIONCHANGE) LocationChanged?.Invoke(hwnd);
    }

    public void Dispose()
    {
        _thread.Invoke(() =>
        {
            foreach (var hook in _hooks) UnhookWinEvent(hook);
            _hooks.Clear();
            return 0;
        });
        _thread.Dispose();
    }
}
