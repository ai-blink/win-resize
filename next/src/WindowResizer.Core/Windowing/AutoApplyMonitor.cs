using WindowResizer.Core.Profiles;

namespace WindowResizer.Core.Windowing;

/// <summary>감시가 보는 창 하나. 열거는 앱이 하고(이 앱의 창은 뺀다), 이 계층은 값만 본다.</summary>
public sealed record WindowSnapshot(nint Handle, WindowInfo Info, PixelRect Rect, bool IsMinimized);

/// <summary>새 창에 프로필을 적용한 결과. 감시 스레드에서 알린다.</summary>
public sealed record AutoApplyResult(string ProfileId, Profile Profile, nint Window, string Title, bool Success);

/// <summary>새 창 자동 적용이 쓰는 규칙(순수). PyQt5 <c>window_monitor.py</c> 의 판정을 옮겼다.</summary>
public static class AutoApplyPolicy
{
    /// <summary>감시할 창인가: 최소화되지 않았고, 제목이 두 글자 이상이고, 100 x 100 이상(PyQt5 <c>_should_monitor_window</c>).</summary>
    public static bool IsEligible(WindowSnapshot window) =>
        !window.IsMinimized &&
        (window.Info.Title ?? "").Trim().Length >= 2 &&
        window.Rect.Width >= 100 && window.Rect.Height >= 100;

    /// <summary>자동 적용 대상 프로필인가: 켜져 있고, 자동 적용이 켜져 있고, 적용할 자리가 있다.</summary>
    public static bool IsAutoApply(Profile profile) =>
        profile is { Enabled: true, AutoApply: true, MatchingCriteria: not null } && profile.WindowConfig is { } c && c.IsValid();

    /// <summary>
    /// 매칭 방식의 구체성 점수. 창 하나에 프로필이 여럿 맞으면 점수가 높은 하나만 적용한다 - 전체 경로가 가장 구체적이고
    /// 제목 일부가 가장 느슨하다(PyQt5 는 경로 120, 프로세스 80, 제목 완전 일치 100, 부분 일치 50). 같으면 프로필의 우선순위
    /// (클수록 먼저), 그래도 같으면 이름 순.
    /// </summary>
    public static int Score(MatchingCriteria criteria) => criteria.Strategy switch
    {
        MatchingStrategy.Combined => 130,
        MatchingStrategy.ExecutablePath => 120,
        MatchingStrategy.ExactTitle => 100,
        MatchingStrategy.ProcessName => 80,
        MatchingStrategy.TitleRegex => 60,
        MatchingStrategy.TitleContains => 50,
        _ => 0,
    };

    public static (string Id, Profile Profile)? Pick(IEnumerable<(string Id, Profile Profile)> profiles, WindowInfo window) =>
        profiles.Where(p => p.Profile.Matches(window))
            .OrderByDescending(p => Score(p.Profile.MatchingCriteria!))
            .ThenByDescending(p => p.Profile.MatchingCriteria!.Priority)
            .ThenBy(p => p.Profile.Name, StringComparer.OrdinalIgnoreCase)
            .Cast<(string Id, Profile Profile)?>()
            .FirstOrDefault();
}

/// <summary>새 창 자동 적용을 앱이 켜고 끄는 데 쓰는 창구(뷰모델이 문서 변경마다 부른다).</summary>
public interface IAutoApplyMonitor : IDisposable
{
    /// <summary>자동 적용 대상 프로필 목록을 바꾼다. 비어 있으면 감시를 멈추고, 비어 있다가 생기면 그 시점에 열려 있는 창을 기준선으로 삼는다.</summary>
    void SetProfiles(IReadOnlyList<(string Id, Profile Profile)> profiles);

    int ProfileCount { get; }
    event Action<AutoApplyResult>? Applied;
}

/// <summary>
/// 새 창 자동 적용(D-036). 1초마다 창 목록을 보고, <b>감시를 켠 뒤에 새로 나타난</b> 창에만 프로필을 적용한다 -
/// 켤 때 이미 열려 있던 창은 기준선이라 건드리지 않는다(PyQt5 와 같다. 그런 창은 전체 적용이나 단축키로 적용한다).
///
/// PyQt5 와 다른 점(의미를 부여한 설정): 적용 지연은 프로필의 <c>apply_delay</c>(기본 2초), 시도 횟수와 간격은 프로필의
/// <c>max_retries</c>(기본 3)와 <c>retry_delay</c>(기본 0.5초)를 쓴다. PyQt5 는 이 값들을 읽지 않고 전역 상수를 썼다.
/// 재시도는 스레드를 재우지 않고 다음 검사 때 다시 한다. 매칭은 적용 직전의 제목으로 한다 - 창이 뜬 뒤에 제목을 붙이는
/// 프로그램이 많다. 30초 안에 맞는 프로필이 없으면 그 창은 그만 본다. 적용에 성공하거나 시도를 다 쓰면 그 창은 사라질
/// 때까지 다시 적용하지 않는다. <c>only_on_startup</c> 과 <c>auto_apply_enabled</c> 는 PyQt5 도 읽지 않아서 이번에도 뜻이 없다.
/// </summary>
public sealed class AutoApplyMonitor : IAutoApplyMonitor
{
    private const double GiveUpSeconds = 30;

    private sealed class Pending(double detectedAt)
    {
        public double DetectedAt { get; } = detectedAt;
        public double NextAttempt { get; set; }
        public int Attempts { get; set; }
    }

    private readonly Func<IReadOnlyList<WindowSnapshot>> _enumerate;
    private readonly Func<nint, string, Profile, bool> _apply;
    private readonly Func<double> _now;
    private readonly object _gate = new();
    private readonly HashSet<nint> _known = new();
    private readonly Dictionary<nint, Pending> _pending = new();
    private IReadOnlyList<(string Id, Profile Profile)> _profiles = [];
    private Timer? _timer;
    private bool _running;

    /// <param name="apply">창 핸들, 프로필 ID, 프로필을 받아 적용하고 성공 여부를 돌려준다. 감시 스레드에서 불린다.</param>
    public AutoApplyMonitor(Func<IReadOnlyList<WindowSnapshot>> enumerate, Func<nint, string, Profile, bool> apply, Func<double>? now = null)
    {
        _enumerate = enumerate;
        _apply = apply;
        _now = now ?? (() => Environment.TickCount64 / 1000.0);
    }

    public event Action<AutoApplyResult>? Applied;

    public int ProfileCount
    {
        get { lock (_gate) return _profiles.Count; }
    }

    public bool IsRunning
    {
        get { lock (_gate) return _running; }
    }

    /// <summary>주기 검사를 시작한다(1초). 테스트는 <see cref="Tick"/> 을 직접 부른다.</summary>
    public void Start(TimeSpan? interval = null)
    {
        var period = interval ?? TimeSpan.FromSeconds(1);
        _timer ??= new Timer(_ => Tick(), null, period, period);
    }

    public void SetProfiles(IReadOnlyList<(string Id, Profile Profile)> profiles)
    {
        var targets = profiles.Where(p => AutoApplyPolicy.IsAutoApply(p.Profile)).ToList();
        IReadOnlyList<WindowSnapshot>? baseline = null;
        var starting = false;
        lock (_gate) starting = targets.Count > 0 && !_running;
        if (starting) baseline = SafeEnumerate();

        lock (_gate)
        {
            _profiles = targets;
            if (targets.Count == 0)
            {
                _running = false;
                _known.Clear();
                _pending.Clear();
            }
            else if (!_running)
            {
                _running = true;
                _known.Clear();
                _pending.Clear();
                foreach (var w in baseline ?? []) _known.Add(w.Handle);
            }
        }
    }

    /// <summary>한 번 검사한다.</summary>
    public void Tick()
    {
        lock (_gate)
        {
            if (!_running) return;
        }

        var windows = SafeEnumerate().Where(AutoApplyPolicy.IsEligible).ToList();
        var due = new List<(WindowSnapshot Window, string Id, Profile Profile)>();
        lock (_gate)
        {
            if (!_running) return;
            var now = _now();
            var present = windows.Select(w => w.Handle).ToHashSet();
            _known.RemoveWhere(h => !present.Contains(h));
            foreach (var gone in _pending.Keys.Where(h => !present.Contains(h)).ToList()) _pending.Remove(gone);

            foreach (var window in windows)
            {
                if (_known.Add(window.Handle)) _pending[window.Handle] = new Pending(now);
            }

            foreach (var window in windows.Where(w => _pending.ContainsKey(w.Handle)))
            {
                var pending = _pending[window.Handle];
                if (AutoApplyPolicy.Pick(_profiles, window.Info) is not { } best)
                {
                    if (now - pending.DetectedAt > GiveUpSeconds) _pending.Remove(window.Handle);
                    continue;
                }

                var criteria = best.Profile.MatchingCriteria!;
                if (now < pending.DetectedAt + Math.Clamp(criteria.ApplyDelay, 0, 60) || now < pending.NextAttempt) continue;
                due.Add((window, best.Id, best.Profile));
            }
        }

        // 적용은 잠금 밖에서 한다: 적용은 화면 스레드로 넘어가고, 화면 스레드는 SetProfiles 로 이 잠금을 잡을 수 있다.
        var results = new List<AutoApplyResult>();
        foreach (var (window, id, profile) in due)
        {
            var ok = _apply(window.Handle, id, profile);
            lock (_gate)
            {
                if (!_pending.TryGetValue(window.Handle, out var pending)) continue;
                pending.Attempts++;
                var criteria = profile.MatchingCriteria!;
                if (ok || pending.Attempts >= Math.Max(1, criteria.MaxRetries))
                {
                    _pending.Remove(window.Handle);
                    results.Add(new AutoApplyResult(id, profile, window.Handle, window.Info.Title ?? "", ok));
                }
                else
                {
                    pending.NextAttempt = _now() + Math.Clamp(criteria.RetryDelay, 0.1, 10);
                }
            }
        }
        foreach (var result in results) Applied?.Invoke(result);
    }

    private IReadOnlyList<WindowSnapshot> SafeEnumerate()
    {
        try
        {
            return _enumerate();
        }
        catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception or UnauthorizedAccessException)
        {
            return [];   // 프로세스 정보를 못 읽는 순간의 예외로 감시가 죽지 않게. 다음 검사에 다시 본다
        }
    }

    public void Dispose()
    {
        _timer?.Dispose();
        _timer = null;
    }
}
