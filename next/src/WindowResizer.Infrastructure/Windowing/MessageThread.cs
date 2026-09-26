using System.Collections.Concurrent;
using static WindowResizer.Infrastructure.Windowing.NativeMethods;

namespace WindowResizer.Infrastructure.Windowing;

/// <summary>
/// Win32 메시지 루프를 가진 전용 스레드.
///
/// 두 곳이 이것을 필요로 한다. NULL 창으로 등록한 단축키의 <c>WM_HOTKEY</c> 는 등록한 스레드의
/// 메시지 큐로 오고, <c>WINEVENT_OUTOFCONTEXT</c> 훅 콜백은 훅을 건 스레드가 메시지를 펌프할 때만
/// 불린다. 그래서 등록/해제와 콜백이 전부 이 스레드 위에서 일어나야 한다.
/// UI 프레임워크에 기대지 않으므로 Infrastructure 가 WPF 를 몰라도 된다.
/// 콜백은 이 스레드에서 불린다 - UI 로 넘기는 것은 호출자 몫이다.
/// </summary>
internal sealed class MessageThread : IDisposable
{
    private readonly Thread _thread;
    private readonly ConcurrentQueue<Action> _work = new();
    private readonly TaskCompletionSource<uint> _started = new(TaskCreationOptions.RunContinuationsAsynchronously);
    private readonly Action<MSG>? _onThreadMessage;
    private uint _threadId;

    /// <param name="onThreadMessage">창에 속하지 않은 스레드 메시지(예: <c>WM_HOTKEY</c>)를 받는다.</param>
    public MessageThread(string name, Action<MSG>? onThreadMessage = null)
    {
        _onThreadMessage = onThreadMessage;
        _thread = new Thread(Run) { IsBackground = true, Name = name };
        _thread.Start();
        _threadId = _started.Task.GetAwaiter().GetResult();
    }

    /// <summary>이 스레드 위에서 실행하고 결과를 기다린다.</summary>
    public T Invoke<T>(Func<T> func)
    {
        if (Environment.CurrentManagedThreadId == _thread.ManagedThreadId) return func();

        var done = new TaskCompletionSource<T>(TaskCreationOptions.RunContinuationsAsynchronously);
        _work.Enqueue(() =>
        {
            try { done.SetResult(func()); }
            catch (Exception ex) { done.SetException(ex); }
        });
        if (!PostThreadMessageW(_threadId, WM_APP, 0, 0))
            throw new InvalidOperationException("메시지 스레드가 멈춰 있다");
        return done.Task.GetAwaiter().GetResult();
    }

    private void Run()
    {
        // 첫 Peek 가 이 스레드의 메시지 큐를 만든다. 그 전에는 PostThreadMessage 가 실패한다.
        PeekMessageW(out _, 0, 0, 0, PM_NOREMOVE);
        _started.SetResult(GetCurrentThreadId());

        while (GetMessageW(out var msg, 0, 0, 0) > 0)
        {
            if (msg.hwnd == 0 && msg.message == WM_APP)
            {
                while (_work.TryDequeue(out var action)) action();
                continue;
            }

            if (msg.hwnd == 0) _onThreadMessage?.Invoke(msg);

            TranslateMessage(ref msg);
            DispatchMessageW(ref msg);
        }
    }

    public void Dispose()
    {
        if (_threadId != 0 && _thread.IsAlive)
        {
            PostThreadMessageW(_threadId, WM_QUIT, 0, 0);
            _thread.Join(TimeSpan.FromSeconds(2));
        }
        _threadId = 0;
    }
}
