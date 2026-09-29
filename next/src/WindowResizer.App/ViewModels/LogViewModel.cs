using System.Collections.ObjectModel;
using System.IO;
using System.Text;
using WindowResizer.App.Mvvm;
using WindowResizer.Core.Diagnostics;

namespace WindowResizer.App.ViewModels;

/// <summary>목록 한 줄. 색은 수준이 정하지만 글자(WARNING, ERROR)가 함께 있어 색에만 기대지 않는다.</summary>
public sealed record LogRow(string Text, LogLevel Level);

/// <summary>걸러 보기 콤보의 한 칸.</summary>
public sealed record LogLevelOption(LogLevel Level, string Display);

/// <summary>
/// 로그 페이지의 로그 쪽(PyQt5 디버그 창의 대체). 기록 자체는 Core <see cref="ActivityLog"/> 가 갖고, 여기는 화면에 보일
/// 줄(수준으로 거른 것), 걸러 보기·최대 개수·자동 스크롤, 지우기·복사·내보내기를 맡는다.
///
/// 복사와 내보내기는 <b>지금 보이는 줄</b>만 준다(걸러 놓고 복사했는데 안 보이는 줄이 딸려 오지 않게).
/// </summary>
public sealed class LogViewModel : ObservableObject
{
    /// <summary>최대 줄 수 콤보의 값. 100-10000 안이다(<see cref="ActivityLog.MaxEntries"/> 가 같은 범위로 맞춘다).</summary>
    public static IReadOnlyList<int> MaxOptions { get; } = [100, 500, 1000, 5000, 10000];

    private readonly ActivityLog _log;
    private readonly IDialogService? _dialogs;
    private readonly Func<string, string> _text;
    private readonly Action<string, LogLevel> _status;
    private readonly Func<DateTime> _now;

    private LogLevel _minLevel = LogLevel.Info;
    private bool _autoScroll = true;
    private IReadOnlyList<LogLevelOption> _levelOptions;

    public LogViewModel(ActivityLog log, IDialogService? dialogs, Func<string, string> text,
        Action<string, LogLevel> status, Func<DateTime>? now = null)
    {
        _log = log;
        _dialogs = dialogs;
        _text = text;
        _status = status;
        _now = now ?? (() => DateTime.Now);
        _levelOptions = BuildLevelOptions();

        _log.Added += OnAdded;
        _log.Trimmed += Rebuild;
        _log.Cleared += () => { Rows.Clear(); OnCountChanged(); };

        ClearCommand = new RelayCommand(_log.Clear);
        CopyCommand = new RelayCommand(Copy);
        ExportCommand = new RelayCommand(Export);
        Rebuild();
    }

    public ObservableCollection<LogRow> Rows { get; } = new();

    public System.Windows.Input.ICommand ClearCommand { get; }
    public System.Windows.Input.ICommand CopyCommand { get; }
    public System.Windows.Input.ICommand ExportCommand { get; }

    public IReadOnlyList<LogLevelOption> LevelOptions
    {
        get => _levelOptions;
        private set => Set(ref _levelOptions, value);
    }

    /// <summary>이 수준 이상만 보인다.</summary>
    public LogLevel MinLevel
    {
        get => _minLevel;
        set
        {
            if (!Set(ref _minLevel, value)) return;
            Rebuild();
        }
    }

    public int MaxEntries
    {
        get => _log.MaxEntries;
        set
        {
            if (_log.MaxEntries == Math.Clamp(value, ActivityLog.MinMaxEntries, ActivityLog.MaxMaxEntries)) return;
            _log.MaxEntries = value;
            OnPropertyChanged();
        }
    }

    public bool AutoScroll { get => _autoScroll; set => Set(ref _autoScroll, value); }

    public string CountText => string.Format(_text("Log.Count"), Rows.Count);

    public bool IsEmpty => Rows.Count == 0;

    /// <summary>표시 언어가 바뀌었다 - 콤보 이름과 개수 문구를 새 언어로 다시 만든다. 기록된 줄은 그때의 언어 그대로다.</summary>
    public void RefreshTexts()
    {
        LevelOptions = BuildLevelOptions();
        OnCountChanged();
    }

    private List<LogLevelOption> BuildLevelOptions() =>
    [
        new(LogLevel.Info, _text("Log.Level.Info")),
        new(LogLevel.Warning, _text("Log.Level.Warning")),
        new(LogLevel.Error, _text("Log.Level.Error")),
    ];

    private void OnAdded(LogEntry entry)
    {
        if (entry.Level < _minLevel) return;
        Rows.Add(new LogRow(entry.Format(), entry.Level));
        OnCountChanged();
    }

    private void Rebuild()
    {
        Rows.Clear();
        foreach (var entry in _log.AtLeast(_minLevel)) Rows.Add(new LogRow(entry.Format(), entry.Level));
        OnCountChanged();
    }

    private void OnCountChanged()
    {
        OnPropertyChanged(nameof(CountText));
        OnPropertyChanged(nameof(IsEmpty));
    }

    private void Copy()
    {
        if (Rows.Count == 0)
        {
            _status(_text("Status.LogNothingToCopy"), LogLevel.Info);
            return;
        }
        var copied = _dialogs?.CopyToClipboard(_log.Text(_minLevel)) ?? false;
        _status(_text(copied ? "Status.LogCopied" : "Status.CopyFailed"), copied ? LogLevel.Info : LogLevel.Warning);
    }

    private void Export()
    {
        if (Rows.Count == 0)
        {
            _status(_text("Status.LogNothingToExport"), LogLevel.Info);
            return;
        }

        var path = _dialogs?.ChooseSaveFile(_text("Log.SaveTitle"), $"windowresizer_log_{_now():yyyyMMdd_HHmmss}.txt", _text("Log.FileFilter"));
        if (path is null) return;

        try
        {
            // 한글이 옛 편집기에서도 깨지지 않게 BOM 을 붙인다.
            File.WriteAllText(path, _log.ExportText(_minLevel, _text("Log.ExportTitle"), _text("Log.Generated")), new UTF8Encoding(true));
            _status(string.Format(_text("Status.LogExported"), path), LogLevel.Info);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            _status(string.Format(_text("Status.LogExportFailed"), ex.Message), LogLevel.Warning);
        }
    }
}
