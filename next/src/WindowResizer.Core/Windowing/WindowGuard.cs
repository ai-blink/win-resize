using WindowResizer.Core.Hotkeys;
using WindowResizer.Core.Profiles;

namespace WindowResizer.Core.Windowing;

/// <summary>프로필을 적용한 창에 잠금(위치·크기)과 마우스 가둠을 거는 서비스(D-035). 프로필 적용이 <see cref="Engage"/> 를 부른다.</summary>
public interface IWindowGuard : IDisposable
{
    /// <summary>
    /// 적용을 마친 창에 프로필의 잠금과 마우스 제한을 건다. 프로필에 둘 다 없으면 이 창에 걸려 있던 것을 푼다
    /// (다른 프로필을 적용하면 앞 프로필의 잠금이 남지 않는다).
    /// </summary>
    void Engage(nint window, string profileId, Profile profile, PixelRect target);

    /// <summary>이 프로필이 건 것을 모두 푼다(해제 단축키). 푼 창 수.</summary>
    int Release(string profileId);

    /// <summary>모든 잠금과 가둠을 푼다.</summary>
    void ReleaseAll();

    /// <summary>지금 잠금이나 가둠이 걸린 창 수.</summary>
    int Count { get; }

    /// <summary>알릴 일(잠금을 포기했다 등). 감시 스레드에서 불린다.</summary>
    event Action<GuardNotice>? Notice;
}

public enum GuardNoticeKind
{
    /// <summary>창을 되돌리지 못하는 일이 반복돼 잠금을 그만뒀다.</summary>
    LockGaveUp,

    /// <summary>가둠 탈출 키로 마우스 제한을 풀었다.</summary>
    ConstraintEscaped,
}

public readonly record struct GuardNotice(GuardNoticeKind Kind, string ProfileName);

/// <summary>커서 제한(<c>ClipCursor</c>) 어댑터. 제한은 시스템 전체가 공유하는 자원이다.</summary>
public interface ICursorConfiner
{
    /// <summary>지금 제한 사각형. 제한이 없으면 가상 화면 전체다.</summary>
    PixelRect? Current();
    bool Confine(PixelRect rect);
    bool Release();
}

/// <summary>잠금이 창을 되돌릴지 판단하는 규칙(순수). PyQt5 <c>enhanced_window_monitor</c> 의 오차 판정을 옮겼다.</summary>
public static class WindowLockPolicy
{
    public readonly record struct Options(int Tolerance, bool RestoreOnMove, bool RestoreOnResize, int MaxAttempts);

    /// <summary>프로필이 위치나 크기를 잠그는가. 편집 창은 위치 잠금만 다루고, 크기 잠금은 파일에 있는 값만 유효하다.</summary>
    public static bool WantsLock(Profile profile) =>
        profile.LockPosition || profile.LockSize || profile.LockWidth || profile.LockHeight;

    public static Options OptionsOf(Profile profile)
    {
        var r = profile.AutoRestore;
        // 빠진 키의 기본값은 PyQt5 와 같다: 오차 5px, 움직임·크기 변화 둘 다 되돌림, 시도 50회. 편집 창이 저장하는 -1 은 무제한.
        return new Options(
            r?.EffectiveTolerance ?? 5,
            r?.EffectiveRestoreOnMove ?? true,
            r?.EffectiveRestoreOnResize ?? true,
            r?.EffectiveMaxAttempts ?? 50);
    }

    /// <summary>
    /// 목표와 지금 자리를 비교한다. 위치(x, y)와 크기(폭, 높이)를 따로 보고, 각각 <paramref name="options"/> 의 오차를 넘고
    /// 그 종류를 되돌리도록 켜 두었을 때만 되돌린다. PyQt5 와 같이 되돌릴 때는 자리 전체(x, y, 폭, 높이)를 목표로 되돌린다.
    /// </summary>
    public static bool NeedsRestore(PixelRect target, PixelRect current, Options options)
    {
        var moved = Math.Abs(current.X - target.X) > options.Tolerance || Math.Abs(current.Y - target.Y) > options.Tolerance;
        var resized = Math.Abs(current.Width - target.Width) > options.Tolerance || Math.Abs(current.Height - target.Height) > options.Tolerance;
        return (moved && options.RestoreOnMove) || (resized && options.RestoreOnResize);
    }
}

/// <summary>
/// 창 잠금과 마우스 가둠(D-035). 폴링 한 곳(<see cref="Tick"/>)이 둘을 모두 돌본다 - 시간 함수를 받아 테스트가 직접 부른다.
///
/// <b>잠금</b>: 적용한 자리(프로필의 자리)를 목표로, 창이 오차를 넘어 벗어나면 되돌린다. 최대화·최소화된 창은 건드리지
/// 않는다(사용자가 일부러 바꾼 상태와 싸우지 않는다). 되돌리기가 실패하면 시도 횟수를 세고, 프로필의 최대 시도(-1 은
/// 무제한)에 이르면 그 창의 잠금을 그만두고 알린다. 실패가 이어지면 검사 간격을 늘려 관리자 권한 창 같은 곳을 두드리지 않는다.
///
/// <b>가둠</b>: 제한은 시스템 전체 자원이라 한 번에 한 창만 건다. 대상 창이 전경일 때 그 창 사각형으로 가두고, 전경을 잃으면
/// 풀고, 돌아오면 다시 가둔다(D-035: PyQt5 는 전환해도 풀지 않았다). 프로필의 탈출 키를 누르면 그 창의 가둠을 다음 적용까지
/// 멈춘다.
/// </summary>
public sealed class WindowGuard : IWindowGuard
{
    private sealed class Entry(string profileId, string profileName)
    {
        public string ProfileId { get; } = profileId;
        public string ProfileName { get; } = profileName;
        public PixelRect? LockTarget { get; set; }
        public WindowLockPolicy.Options LockOptions { get; set; }
        public int Attempts { get; set; }
        public int ConsecutiveFailures { get; set; }
        public int SkipTicks { get; set; }
        public bool Constrain { get; set; }
        public HotkeyCombination? Escape { get; set; }
        public bool Escaped { get; set; }
    }

    /// <summary>실패가 이 횟수 이어지면 검사 간격을 늘린다.</summary>
    private const int BackoffAfterFailures = 8;
    private const int BackoffTicks = 20;

    private readonly IWindowOperations _windows;
    private readonly ICursorConfiner _cursor;
    private readonly Func<nint> _foreground;
    private readonly Func<int, bool> _isKeyDown;
    private readonly object _gate = new();
    private readonly Dictionary<nint, Entry> _entries = new();
    private Timer? _timer;
    private nint _clippedBy;

    public WindowGuard(IWindowOperations windows, ICursorConfiner cursor, Func<nint> foreground, Func<int, bool> isKeyDown)
    {
        _windows = windows;
        _cursor = cursor;
        _foreground = foreground;
        _isKeyDown = isKeyDown;
    }

    public event Action<GuardNotice>? Notice;

    public int Count
    {
        get { lock (_gate) return _entries.Count; }
    }

    /// <summary>주기 검사를 시작한다(250ms). 테스트는 이것 대신 <see cref="Tick"/> 을 직접 부른다.</summary>
    public void Start(TimeSpan? interval = null)
    {
        var period = interval ?? TimeSpan.FromMilliseconds(250);
        _timer ??= new Timer(_ => Tick(), null, period, period);
    }

    public void Engage(nint window, string profileId, Profile profile, PixelRect target)
    {
        var wantsLock = WindowLockPolicy.WantsLock(profile);
        var wantsConstraint = profile.MouseConstraint;

        lock (_gate)
        {
            if (!wantsLock && !wantsConstraint)
            {
                Remove(window);
                return;
            }

            // 다른 프로필을 적용하면 앞 것을 갈아 끼운다 - 가둠 상태(탈출)도 새로 시작한다.
            if (_clippedBy == window) ReleaseCursor();
            var entry = new Entry(profileId, profile.Name)
            {
                Constrain = wantsConstraint,
                Escape = ParseEscape(profile.ConstraintEscapeKey),
            };
            if (wantsLock)
            {
                entry.LockTarget = target;
                entry.LockOptions = WindowLockPolicy.OptionsOf(profile);
            }
            _entries[window] = entry;
        }
    }

    public int Release(string profileId)
    {
        lock (_gate)
        {
            var windows = _entries.Where(e => e.Value.ProfileId == profileId).Select(e => e.Key).ToList();
            foreach (var window in windows) Remove(window);
            return windows.Count;
        }
    }

    public void ReleaseAll()
    {
        lock (_gate)
        {
            _entries.Clear();
            ReleaseCursor();
        }
    }

    /// <summary>한 번 검사한다. 잠금은 창마다, 가둠은 전경 창 하나에 대해.</summary>
    public void Tick()
    {
        var notices = new List<GuardNotice>();
        lock (_gate)
        {
            foreach (var (window, entry) in _entries.ToList())
            {
                if (!_windows.IsWindow(window))
                {
                    Remove(window);
                    continue;
                }
                if (entry.LockTarget is not null) CheckLock(window, entry, notices);
            }
            CheckConstraint(notices);
        }
        foreach (var notice in notices) Notice?.Invoke(notice);
    }

    private void CheckLock(nint window, Entry entry, List<GuardNotice> notices)
    {
        if (entry.SkipTicks > 0)
        {
            entry.SkipTicks--;
            return;
        }
        // 사용자가 일부러 최대화나 최소화한 창은 되돌리지 않는다(최소화된 창의 좌표는 화면 밖 값이다).
        if (_windows.IsMaximized(window) || _windows.IsMinimized(window)) return;
        if (_windows.GetRect(window) is not { } current) return;

        var target = entry.LockTarget!.Value;
        if (!WindowLockPolicy.NeedsRestore(target, current, entry.LockOptions))
        {
            entry.ConsecutiveFailures = 0;
            return;
        }

        _windows.Move(window, target);
        var after = _windows.GetRect(window);
        if (after is { } r && !WindowLockPolicy.NeedsRestore(target, r, entry.LockOptions))
        {
            entry.ConsecutiveFailures = 0;
            return;
        }

        // 되돌리지 못했다(관리자 권한 창, 최소 크기를 강제하는 창). 세어서 포기하거나 검사 간격을 늘린다.
        entry.Attempts++;
        entry.ConsecutiveFailures++;
        if (entry.LockOptions.MaxAttempts > 0 && entry.Attempts >= entry.LockOptions.MaxAttempts)
        {
            entry.LockTarget = null;
            notices.Add(new GuardNotice(GuardNoticeKind.LockGaveUp, entry.ProfileName));
            if (!entry.Constrain) Remove(window);
        }
        else if (entry.ConsecutiveFailures >= BackoffAfterFailures)
        {
            entry.SkipTicks = BackoffTicks;
        }
    }

    private void CheckConstraint(List<GuardNotice> notices)
    {
        var foreground = _foreground();

        // 우리가 가둔 창이 전경을 잃었거나 없어졌으면 푼다.
        if (_clippedBy != 0 && (_clippedBy != foreground || !_entries.ContainsKey(_clippedBy)))
            ReleaseCursor();

        if (foreground == 0 || !_entries.TryGetValue(foreground, out var entry) || !entry.Constrain || entry.Escaped) return;

        // 탈출 키: 누르고 있으면 이 창의 가둠을 다음 적용까지 멈춘다.
        if (entry.Escape is { } escape && IsDown(escape))
        {
            entry.Escaped = true;
            if (_clippedBy == foreground) ReleaseCursor();
            notices.Add(new GuardNotice(GuardNoticeKind.ConstraintEscaped, entry.ProfileName));
            return;
        }

        if (_windows.IsMinimized(foreground) || _windows.GetRect(foreground) is not { } rect) return;
        if (_clippedBy == foreground && _cursor.Current() == rect) return;   // 이미 이 사각형에 갇혀 있다

        if (_cursor.Confine(rect)) _clippedBy = foreground;
    }

    private bool IsDown(HotkeyCombination combination)
    {
        var m = combination.Modifiers;
        if ((m & HotkeyModifiers.Control) != 0 && !_isKeyDown(0x11)) return false;
        if ((m & HotkeyModifiers.Alt) != 0 && !_isKeyDown(0x12)) return false;
        if ((m & HotkeyModifiers.Shift) != 0 && !_isKeyDown(0x10)) return false;
        if ((m & HotkeyModifiers.Win) != 0 && !_isKeyDown(0x5B) && !_isKeyDown(0x5C)) return false;
        return _isKeyDown(combination.VirtualKey);
    }

    private static HotkeyCombination? ParseEscape(string? text)
    {
        if (string.IsNullOrWhiteSpace(text)) return null;
        try
        {
            return HotkeyCombination.Parse(text);
        }
        catch (FormatException)
        {
            return null;   // 못 읽는 키는 탈출 키가 없는 것으로 - 해제 단축키가 남아 있다
        }
    }

    private void Remove(nint window)
    {
        _entries.Remove(window);
        if (_clippedBy == window) ReleaseCursor();
    }

    private void ReleaseCursor()
    {
        if (_clippedBy == 0) return;
        _cursor.Release();
        _clippedBy = 0;
    }

    public void Dispose()
    {
        _timer?.Dispose();
        _timer = null;
        ReleaseAll();
    }
}

/// <summary>걸지 않는 서비스. 테스트와 가드가 없는 구성에서 쓴다.</summary>
public sealed class NullWindowGuard : IWindowGuard
{
    public int Count => 0;
    public event Action<GuardNotice>? Notice { add { } remove { } }
    public void Engage(nint window, string profileId, Profile profile, PixelRect target) { }
    public int Release(string profileId) => 0;
    public void ReleaseAll() { }
    public void Dispose() { }
}
