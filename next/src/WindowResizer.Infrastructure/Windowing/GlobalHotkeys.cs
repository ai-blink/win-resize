using System.Runtime.InteropServices;
using WindowResizer.Core.Hotkeys;
using static WindowResizer.Infrastructure.Windowing.NativeMethods;

namespace WindowResizer.Infrastructure.Windowing;

/// <summary>
/// 전역 단축키. PyQt5 와 같이 <c>RegisterHotKey(NULL, ...)</c> 로 스레드 큐에 등록한다
/// (<c>hotkey_manager.py</c> register_hotkey). <c>MOD_NOREPEAT</c> 는 PyQt5 도 쓰지 않아 붙이지 않는다.
/// <see cref="Pressed"/> 는 전용 메시지 스레드에서 불린다.
/// </summary>
public sealed class GlobalHotkeys : IDisposable
{
    private readonly MessageThread _thread;
    private readonly Dictionary<int, HotkeyCombination> _registered = new();
    private int _nextId = 1;

    public GlobalHotkeys()
    {
        _thread = new MessageThread("WindowResizer.Hotkeys", OnThreadMessage);
    }

    /// <summary>등록 id 와 함께 눌린 조합을 알린다.</summary>
    public event Action<int, HotkeyCombination>? Pressed;

    /// <summary>
    /// 등록한다. 성공하면 id, 실패하면 null 과 Win32 오류 코드. 다른 프로그램이 같은 조합을 이미
    /// 잡고 있으면 1409(ERROR_HOTKEY_ALREADY_REGISTERED)다.
    /// </summary>
    public int? Register(HotkeyCombination combination, out int errorCode)
    {
        var (id, error) = _thread.Invoke(() =>
        {
            var candidate = _nextId++;
            if (RegisterHotKey(0, candidate, (uint)combination.Modifiers, (uint)combination.VirtualKey))
            {
                _registered[candidate] = combination;
                return (candidate, 0);
            }
            return ((int?)null, Marshal.GetLastPInvokeError());
        });
        errorCode = error;
        return id;
    }

    public bool Unregister(int id) => _thread.Invoke(() =>
    {
        _registered.Remove(id);
        return UnregisterHotKey(0, id);
    });

    private void OnThreadMessage(MSG msg)
    {
        if (msg.message != WM_HOTKEY) return;
        var id = (int)msg.wParam;
        if (_registered.TryGetValue(id, out var combination)) Pressed?.Invoke(id, combination);
    }

    public void Dispose()
    {
        _thread.Invoke(() =>
        {
            foreach (var id in _registered.Keys) UnregisterHotKey(0, id);
            _registered.Clear();
            return 0;
        });
        _thread.Dispose();
    }
}
