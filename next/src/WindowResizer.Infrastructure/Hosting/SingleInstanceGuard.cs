namespace WindowResizer.Infrastructure.Hosting;

/// <summary>
/// 같은 Windows 세션에서 앱을 하나만 띄운다(PyQt5 <c>run_gui.py</c> 와 같은 뮤텍스 이름 - 옛 앱과 새 앱도 동시에 못 뜬다).
/// PyQt5 는 둘째 실행에 영어 메시지 상자만 띄우고 끝났는데, 트레이로 숨은 첫 앱이 앞으로 나오지 않아 사용자에게는
/// 아무 일도 없어 보였다. 여기서는 둘째 실행이 첫 앱에 신호를 보내 창을 앞으로 나오게 한다.
/// 이름은 테스트와 라이브 검증이 실사용 앱과 겹치지 않게 바꿀 수 있다(<c>--instance-key</c>).
/// </summary>
public sealed class SingleInstanceGuard : IDisposable
{
    public const string DefaultName = "WindowResizer.SingleInstance";

    private readonly Mutex _mutex;
    private readonly EventWaitHandle _signal;
    private readonly CancellationTokenSource _stop = new();
    private Thread? _listener;

    private SingleInstanceGuard(Mutex mutex, EventWaitHandle signal, bool isFirst)
    {
        _mutex = mutex;
        _signal = signal;
        IsFirst = isFirst;
    }

    /// <summary>이 프로세스가 첫 실행인가.</summary>
    public bool IsFirst { get; }

    public static SingleInstanceGuard Acquire(string name = DefaultName)
    {
        var mutex = new Mutex(initiallyOwned: true, $@"Local\{name}", out var createdNew);
        var signal = new EventWaitHandle(false, EventResetMode.AutoReset, $@"Local\{name}.Show");
        return new SingleInstanceGuard(mutex, signal, createdNew);
    }

    /// <summary>첫 실행에게 "창을 보여 달라"고 알린다. 둘째 실행이 부른다.</summary>
    public void SignalFirst() => _signal.Set();

    /// <summary>둘째 실행의 신호를 기다려 <paramref name="onSignal"/> 을 부른다(다른 스레드에서 불린다). 첫 실행만 쓴다.</summary>
    public void Listen(Action onSignal)
    {
        if (!IsFirst || _listener is not null) return;
        _listener = new Thread(() =>
        {
            var handles = new[] { _signal, _stop.Token.WaitHandle };
            while (WaitHandle.WaitAny(handles) == 0) onSignal();
        })
        { IsBackground = true, Name = "single-instance-listener" };
        _listener.Start();
    }

    public void Dispose()
    {
        _stop.Cancel();
        _listener?.Join(1000);
        if (IsFirst)
        {
            try { _mutex.ReleaseMutex(); } catch (ApplicationException) { /* 다른 스레드가 만든 뮤텍스 - 프로세스가 끝나면 풀린다 */ }
        }
        _mutex.Dispose();
        _signal.Dispose();
        _stop.Dispose();
    }
}
