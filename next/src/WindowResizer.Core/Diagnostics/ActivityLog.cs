using System.Text;

namespace WindowResizer.Core.Diagnostics;

/// <summary>기록의 무게. 숫자가 클수록 심하다 - "경고 이상" 같은 걸러 보기가 이 순서를 쓴다.</summary>
public enum LogLevel
{
    Info = 0,
    Warning = 1,
    Error = 2,
}

/// <summary>기록 한 줄.</summary>
public sealed record LogEntry(DateTime Time, LogLevel Level, string Message)
{
    /// <summary>화면과 내보내기에서 같은 모양: <c>[14:03:22] WARNING: 문구</c>. PyQt5 디버그 창과 같은 틀이다.</summary>
    public string Format() => $"[{Time:HH:mm:ss}] {Level.ToString().ToUpperInvariant()}: {Message}";
}

/// <summary>
/// 앱이 무엇을 했는지의 기록(로그 페이지). PyQt5 디버그 창은 파이썬 로깅 전체를 받았지만 새 앱에는 로깅이 없어서,
/// 사용자가 상태 줄에서 본 문구와 잡히지 않은 오류를 여기 쌓는다. 표준 로깅 프레임워크는 들이지 않는다.
///
/// 오래된 것부터 버려 <see cref="MaxEntries"/> 개를 넘지 않는다. UI 스레드에서만 쓴다.
/// </summary>
public sealed class ActivityLog
{
    public const int MinMaxEntries = 100;
    public const int MaxMaxEntries = 10000;
    public const int DefaultMaxEntries = 1000;

    private readonly List<LogEntry> _entries = new();
    private readonly Func<DateTime> _now;
    private int _maxEntries = DefaultMaxEntries;

    /// <param name="now">현재 시각. 테스트가 고정한다.</param>
    public ActivityLog(Func<DateTime>? now = null) => _now = now ?? (() => DateTime.Now);

    public IReadOnlyList<LogEntry> Entries => _entries;

    /// <summary>줄 하나가 더해졌다(더한 뒤 오래된 것을 버렸으면 <see cref="Trimmed"/> 가 이어서 온다).</summary>
    public event Action<LogEntry>? Added;

    /// <summary>오래된 줄을 버렸다(최대 개수를 넘었거나 줄였다).</summary>
    public event Action? Trimmed;

    public event Action? Cleared;

    /// <summary>100-10000 으로 맞춘다. 줄이면 오래된 것부터 바로 버린다.</summary>
    public int MaxEntries
    {
        get => _maxEntries;
        set
        {
            _maxEntries = Math.Clamp(value, MinMaxEntries, MaxMaxEntries);
            Trim();
        }
    }

    public LogEntry Add(LogLevel level, string message)
    {
        var entry = new LogEntry(_now(), level, message);
        _entries.Add(entry);
        Added?.Invoke(entry);
        Trim();
        return entry;
    }

    public void Clear()
    {
        if (_entries.Count == 0) return;
        _entries.Clear();
        Cleared?.Invoke();
    }

    /// <summary>이 수준 이상인 줄들.</summary>
    public IEnumerable<LogEntry> AtLeast(LogLevel minimum) => _entries.Where(e => e.Level >= minimum);

    /// <summary>
    /// 파일과 클립보드용 본문. 내보내기는 머리말(제목, 생성 시각)을 붙이고 복사는 줄만 준다.
    /// </summary>
    public string Text(LogLevel minimum) => string.Join(Environment.NewLine, AtLeast(minimum).Select(e => e.Format()));

    public string ExportText(LogLevel minimum, string title, string generatedLabel)
    {
        var text = new StringBuilder();
        text.AppendLine(title);
        text.AppendLine($"{generatedLabel}: {_now():yyyy-MM-dd HH:mm:ss}");
        text.AppendLine(new string('=', 50));
        text.AppendLine();
        foreach (var entry in AtLeast(minimum)) text.AppendLine(entry.Format());
        return text.ToString();
    }

    private void Trim()
    {
        var extra = _entries.Count - _maxEntries;
        if (extra <= 0) return;
        _entries.RemoveRange(0, extra);
        Trimmed?.Invoke();
    }
}
