using System.Windows.Input;
using WindowResizer.App.Mvvm;
using WindowResizer.Core.Profiles;
using WindowResizer.Core.Windowing;

namespace WindowResizer.App.ViewModels;

/// <summary>편집 창 사이드바 항목. 순서는 사이드바와 같다(계획 4.4).</summary>
public enum EditorPage
{
    General,
    Target,
    Position,
    RunMethod,
    Advanced,
}

/// <summary>
/// 프로필 편집 창(계획 4.4). <b>복사본</b>을 받아 필드로 풀어 두고, <see cref="TrySave"/> 가 검사를 통과했을 때만
/// 복사본에 되쓴다. 문서에 넣는 것은 <see cref="MainViewModel"/> 의 일이다 - 취소하면 아무것도 안 바뀐다.
///
/// 편집 창이 다루지 않는 필드(단축키 세트, 자동 복원, 오버레이 생김새, 모르는 키 등)는 복사본에 그대로 남아
/// 저장 뒤에도 사라지지 않는다.
/// </summary>
public sealed class ProfileEditorViewModel : ObservableObject
{
    public static readonly MatchingStrategy[] Strategies =
    [
        MatchingStrategy.ExecutablePath,
        MatchingStrategy.ProcessName,
        MatchingStrategy.TitleContains,
        MatchingStrategy.ExactTitle,
        MatchingStrategy.TitleRegex,
        MatchingStrategy.Combined,
    ];

    private readonly Func<string, bool> _isNameTaken;
    private readonly Func<IReadOnlyList<WindowRow>> _enumerateWindows;
    private readonly IWindowOperations _windows;
    private readonly IDialogService _dialogs;
    private readonly Func<string, string> _text;
    private readonly string _originalName;

    private EditorPage _page;
    private string _name, _description;
    private bool _enabled;
    private MatchingStrategy _strategy;
    private string _executablePath, _processName, _titlePattern;
    private int _x, _y, _width, _height;
    private bool _isMaximized;
    private bool _hotkeyEnabled;
    private string _hotkeyCombination;
    private bool _overlayEnabled, _autoApply;
    private bool _lockPosition, _mouseConstraint, _alwaysOnTop;
    private string _error = "", _message = "";

    /// <param name="isNameTaken">다른 프로필이 이미 쓰는 이름인가(대소문자 무시).</param>
    public ProfileEditorViewModel(
        Profile working,
        EditorPage page,
        Func<string, bool> isNameTaken,
        Func<IReadOnlyList<WindowRow>> enumerateWindows,
        IWindowOperations windows,
        IDialogService dialogs,
        Func<string, string> text)
    {
        Profile = working;
        _page = page;
        _isNameTaken = isNameTaken;
        _enumerateWindows = enumerateWindows;
        _windows = windows;
        _dialogs = dialogs;
        _text = text;
        _originalName = working.Name;

        _name = working.Name;
        _description = working.Description;
        _enabled = working.Enabled;

        var c = working.MatchingCriteria ?? new MatchingCriteria { Strategy = MatchingStrategy.TitleContains };
        _strategy = Strategies.Contains(c.Strategy) ? c.Strategy : MatchingStrategy.TitleContains;
        _executablePath = c.ExecutablePathPattern ?? "";
        _processName = c.ProcessNamePattern ?? "";
        _titlePattern = c.WindowTitlePattern ?? "";

        var w = working.WindowConfig ?? new WindowConfiguration { Width = 800, Height = 600 };
        (_x, _y, _width, _height, _isMaximized) = (w.X, w.Y, w.Width, w.Height, w.IsMaximized);
        _alwaysOnTop = w.AlwaysOnTop;

        _hotkeyEnabled = working.HotkeyEnabled;
        _hotkeyCombination = working.HotkeyCombination;
        _overlayEnabled = working.OverlayStyle?.Enabled ?? false;
        _autoApply = working.AutoApply;
        _lockPosition = working.LockPosition;
        _mouseConstraint = working.MouseConstraint;

        NavigateCommand = new ParameterCommand<EditorPage>(p => Page = p);
        CaptureFromWindowCommand = new RelayCommand(CaptureFromWindow);
    }

    /// <summary>편집 대상 복사본. <see cref="TrySave"/> 가 성공한 뒤에만 편집 값이 들어 있다.</summary>
    public Profile Profile { get; }

    public ICommand NavigateCommand { get; }
    public ICommand CaptureFromWindowCommand { get; }

    public EditorPage Page { get => _page; set => Set(ref _page, value); }

    public string Name { get => _name; set => Set(ref _name, value); }
    public string Description { get => _description; set => Set(ref _description, value); }
    public bool Enabled { get => _enabled; set => Set(ref _enabled, value); }

    public IReadOnlyList<MatchingStrategy> StrategyOptions => Strategies;

    public MatchingStrategy Strategy
    {
        get => _strategy;
        set
        {
            if (!Set(ref _strategy, value)) return;
            OnPropertyChanged(nameof(UsesExecutablePath));
            OnPropertyChanged(nameof(UsesProcessName));
            OnPropertyChanged(nameof(UsesTitle));
        }
    }

    // "켤 수 있으면 켜져 있다"(계획 4.1): 고른 방식이 쓰는 칸만 열린다.
    public bool UsesExecutablePath => _strategy is MatchingStrategy.ExecutablePath or MatchingStrategy.Combined;
    public bool UsesProcessName => _strategy is MatchingStrategy.ProcessName or MatchingStrategy.Combined;
    public bool UsesTitle => _strategy is MatchingStrategy.ExactTitle or MatchingStrategy.TitleContains
        or MatchingStrategy.TitleRegex or MatchingStrategy.Combined;

    public string ExecutablePath { get => _executablePath; set => Set(ref _executablePath, value); }
    public string ProcessName { get => _processName; set => Set(ref _processName, value); }
    public string TitlePattern { get => _titlePattern; set => Set(ref _titlePattern, value); }

    public int X { get => _x; set => Set(ref _x, value); }
    public int Y { get => _y; set => Set(ref _y, value); }
    public int Width { get => _width; set => Set(ref _width, value); }
    public int Height { get => _height; set => Set(ref _height, value); }
    public bool IsMaximized { get => _isMaximized; set => Set(ref _isMaximized, value); }

    public bool HotkeyEnabled { get => _hotkeyEnabled; set => Set(ref _hotkeyEnabled, value); }
    public string HotkeyCombination { get => _hotkeyCombination; set => Set(ref _hotkeyCombination, value); }
    public bool OverlayEnabled { get => _overlayEnabled; set => Set(ref _overlayEnabled, value); }
    public bool AutoApply { get => _autoApply; set => Set(ref _autoApply, value); }

    public bool LockPosition { get => _lockPosition; set => Set(ref _lockPosition, value); }
    public bool MouseConstraint { get => _mouseConstraint; set => Set(ref _mouseConstraint, value); }
    public bool AlwaysOnTop { get => _alwaysOnTop; set => Set(ref _alwaysOnTop, value); }

    /// <summary>저장을 막은 이유. 비어 있으면 문제없다.</summary>
    public string Error { get => _error; private set => Set(ref _error, value); }

    /// <summary>"현재 창에서 가져오기" 결과 한 줄.</summary>
    public string Message { get => _message; private set => Set(ref _message, value); }

    /// <summary>
    /// 검사하고 통과하면 복사본에 되쓴다. 실패하면 <see cref="Error"/> 와 문제 페이지로 옮긴다.
    /// </summary>
    public bool TrySave()
    {
        var problem = Validate();
        if (problem is not null)
        {
            Error = _text(problem.Value.Key);
            Page = problem.Value.Page;
            return false;
        }

        Error = "";
        var p = Profile;
        p.Name = Name.Trim();
        p.Description = Description;
        p.Enabled = Enabled;

        var c = p.MatchingCriteria ?? new MatchingCriteria();
        c.Strategy = Strategy;
        // 고른 방식이 쓰지 않는 칸은 비운다. 남겨 두면 "결합" 으로 바꿨을 때 옛 값이 조용히 조건에 끼어든다.
        c.ExecutablePathPattern = UsesExecutablePath ? NullIfEmpty(ExecutablePath) : null;
        c.ProcessNamePattern = UsesProcessName ? NullIfEmpty(ProcessName) : null;
        c.WindowTitlePattern = UsesTitle ? NullIfEmpty(TitlePattern) : null;
        p.MatchingCriteria = c;

        var w = p.WindowConfig ?? new WindowConfiguration();
        (w.X, w.Y, w.Width, w.Height, w.IsMaximized, w.AlwaysOnTop) = (X, Y, Width, Height, IsMaximized, AlwaysOnTop);
        p.WindowConfig = w;

        p.HotkeyEnabled = HotkeyEnabled;
        p.HotkeyCombination = HotkeyCombination.Trim();
        if (OverlayEnabled || p.OverlayStyle is not null)
        {
            p.OverlayStyle ??= new OverlayStyle();
            p.OverlayStyle.Enabled = OverlayEnabled;
        }
        p.AutoApply = AutoApply;
        p.LockPosition = LockPosition;
        p.MouseConstraint = MouseConstraint;
        return true;
    }

    private (string Key, EditorPage Page)? Validate()
    {
        var name = Name.Trim();
        if (name.Length == 0) return ("Editor.Error.NameEmpty", EditorPage.General);
        var renamed = !string.Equals(name, _originalName.Trim(), StringComparison.OrdinalIgnoreCase);
        if (renamed && _isNameTaken(name)) return ("Editor.Error.NameTaken", EditorPage.General);

        var hasPattern = Strategy switch
        {
            MatchingStrategy.ExecutablePath => ExecutablePath.Trim().Length > 0,
            MatchingStrategy.ProcessName => ProcessName.Trim().Length > 0,
            MatchingStrategy.Combined => (ExecutablePath + ProcessName + TitlePattern).Trim().Length > 0,
            _ => TitlePattern.Trim().Length > 0,
        };
        if (!hasPattern) return ("Editor.Error.PatternEmpty", EditorPage.Target);

        if (Width <= 0 || Height <= 0) return ("Editor.Error.SizeInvalid", EditorPage.Position);

        if (HotkeyEnabled && !Core.Hotkeys.HotkeyCombination.TryParse(HotkeyCombination, out _))
            return ("Editor.Error.HotkeyInvalid", EditorPage.RunMethod);

        return null;
    }

    /// <summary>
    /// 지금 입력한 대상 조건으로 창을 찾아 위치와 크기를 가져온다(D-021). 매칭은 적용과 같은
    /// <see cref="MatchingCriteria.Matches"/> 이고, 여러 개면 조용히 첫 창을 쓰지 않고 사용자가 고른다.
    /// </summary>
    public void CaptureFromWindow()
    {
        var criteria = new MatchingCriteria
        {
            Strategy = Strategy,
            ExecutablePathPattern = UsesExecutablePath ? NullIfEmpty(ExecutablePath) : null,
            ProcessNamePattern = UsesProcessName ? NullIfEmpty(ProcessName) : null,
            WindowTitlePattern = UsesTitle ? NullIfEmpty(TitlePattern) : null,
            CaseSensitive = Profile.MatchingCriteria?.CaseSensitive ?? false,
            RegexFlags = Profile.MatchingCriteria?.RegexFlags ?? 0,
        };

        var candidates = _enumerateWindows().Where(w => criteria.Matches(w.Info)).ToList();
        if (candidates.Count == 0)
        {
            Message = _text("Editor.Capture.NoMatch");
            return;
        }

        var window = candidates.Count == 1 ? candidates[0] : _dialogs.ChooseWindow(candidates);
        if (window is null) return;

        var capture = WindowCapture.Capture(_windows, window.Handle);
        if (!capture.Succeeded)
        {
            Message = string.Format(_text("Status.CaptureRefused"), window.Info.Title, _text("Capture." + capture.Refusal));
            return;
        }

        var c = capture.Configuration!;
        (X, Y, Width, Height, IsMaximized) = (c.X, c.Y, c.Width, c.Height, c.IsMaximized);
        Message = string.Format(_text("Editor.Capture.Done"), window.Info.Title);
    }

    private static string? NullIfEmpty(string value) => value.Trim().Length == 0 ? null : value.Trim();
}
