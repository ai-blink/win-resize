using WindowResizer.App.Mvvm;
using WindowResizer.Core.Settings;

namespace WindowResizer.App.ViewModels;

/// <summary>설정 페이지가 밖에서 받는 것. 전부 없어도 앱은 뜬다(테스트) - 그때는 저장하지 않고 시작 등록은 늘 꺼져 있다.</summary>
/// <param name="Settings">처음 값(저장소에서 읽은 것).</param>
/// <param name="Save">설정 저장. 성공하면 null, 실패하면 원인.</param>
/// <param name="IsStartupEnabled">Windows 시작 때 자동 실행이 등록돼 있는가.</param>
/// <param name="SetStartup">자동 실행을 켜고 끈다. 성공하면 null, 실패하면 원인.</param>
public sealed record SettingsServices(
    AppSettings? Settings = null,
    Func<AppSettings, string?>? Save = null,
    Func<bool>? IsStartupEnabled = null,
    Func<bool, string?>? SetStartup = null);

/// <summary>언어 콤보의 한 칸. 이름은 그 언어 자신의 표기다 - 지금 언어가 무엇이든 찾을 수 있게 번역하지 않는다.</summary>
public sealed record LanguageOption(string Code, string Display);

/// <summary>
/// 설정 페이지(테마, 화면 크기, 언어, 시작 프로그램, 창 크기 기억)의 화면 쪽 주인. 오버레이 페이지와 같은 규율이다:
/// 값을 바꾸면 바로 저장하고 <see cref="Changed"/> 로 알린다(App 이 테마, 배율, 언어를 실제로 적용한다).
/// 저장이 실패해도 화면 값은 유지한다 - 다음 저장이 다시 시도한다.
///
/// 화면 크기만 예외다: 슬라이더를 끄는 동안에는 <b>미리보기만</b> 바뀌고 놓을 때 적용한다. 배율을 적용하면 슬라이더
/// 자신도 커지거나 줄어 손 밑에서 움직이므로 끄는 도중 바로 적용하면 값이 튄다. 키보드와 트랙 클릭은 끄는 것이 아니라
/// 바로 적용한다.
/// </summary>
public sealed class SettingsViewModel : ObservableObject
{
    public static IReadOnlyList<LanguageOption> LanguageOptions { get; } =
    [
        new("ko", "한국어"),
        new("en", "English"),
    ];

    private readonly Func<AppSettings, string?> _save;
    private readonly Func<bool> _isStartupEnabled;
    private readonly Func<bool, string?> _setStartup;
    private readonly Func<string, string> _text;
    private readonly Action<string> _status;

    private int _pendingScale;
    private bool _dragging;
    private bool _startWithWindows;

    public SettingsViewModel(AppSettings settings, Func<AppSettings, string?> save,
        Func<bool> isStartupEnabled, Func<bool, string?> setStartup,
        Func<string, string> text, Action<string> status)
    {
        Settings = settings;
        _save = save;
        _isStartupEnabled = isStartupEnabled;
        _setStartup = setStartup;
        _text = text;
        _status = status;
        _pendingScale = settings.ScalePercent;
        _startWithWindows = isStartupEnabled();
        ResetScaleCommand = new RelayCommand(() => ScalePercent = AppSettings.DefaultScalePercent);
    }

    public AppSettings Settings { get; }

    /// <summary>설정 하나가 바뀌었다. 인자는 속성 이름(테마 <c>Theme</c>, 배율 <c>AppliedScale</c>, 언어 <c>Language</c>).</summary>
    public event Action<string>? Changed;

    public System.Windows.Input.ICommand ResetScaleCommand { get; }

    // --- 테마 ---------------------------------------------------------------------------------

    public bool IsThemeSystem { get => Settings.Theme == ThemeChoice.System; set { if (value) SetTheme(ThemeChoice.System); } }
    public bool IsThemeLight { get => Settings.Theme == ThemeChoice.Light; set { if (value) SetTheme(ThemeChoice.Light); } }
    public bool IsThemeDark { get => Settings.Theme == ThemeChoice.Dark; set { if (value) SetTheme(ThemeChoice.Dark); } }

    private void SetTheme(ThemeChoice choice)
    {
        if (Settings.Theme == choice) return;
        Settings.Theme = choice;
        OnPropertyChanged(nameof(IsThemeSystem));
        OnPropertyChanged(nameof(IsThemeLight));
        OnPropertyChanged(nameof(IsThemeDark));
        Commit("Theme", () => _text(choice switch
        {
            ThemeChoice.Light => "Status.ThemeLight",
            ThemeChoice.Dark => "Status.ThemeDark",
            _ => "Status.ThemeSystem",
        }));
    }

    // --- 화면 크기 ----------------------------------------------------------------------------

    /// <summary>슬라이더가 보는 값(%). 끄는 동안의 값이고, 적용된 값은 <see cref="AppliedScale"/> 이다.</summary>
    public double ScalePercent
    {
        get => _pendingScale;
        set
        {
            var scale = AppSettings.NormalizeScale(value);
            if (scale == _pendingScale) return;
            _pendingScale = scale;
            OnPropertyChanged();
            OnPropertyChanged(nameof(ScaleText));
            OnPropertyChanged(nameof(PreviewFactor));
            if (!_dragging) CommitScale();
        }
    }

    public int AppliedScale => Settings.ScalePercent;

    public string ScaleText => _pendingScale + "%";

    /// <summary>미리보기 견본을 지금 화면에서 몇 배로 그릴지 = 고른 값 / 적용된 값. 페이지 자신이 이미 적용된 배율이다.</summary>
    public double PreviewFactor => _pendingScale / (double)Settings.ScalePercent;

    public void BeginScaleDrag() => _dragging = true;

    public void EndScaleDrag()
    {
        _dragging = false;
        CommitScale();
    }

    private void CommitScale()
    {
        if (_pendingScale == Settings.ScalePercent) return;
        Settings.ScalePercent = _pendingScale;
        OnPropertyChanged(nameof(AppliedScale));
        OnPropertyChanged(nameof(PreviewFactor));
        Commit("AppliedScale", () => string.Format(_text("Status.Scale"), Settings.ScalePercent));
    }

    // --- 언어 ---------------------------------------------------------------------------------

    public string Language
    {
        get => Settings.Language;
        set
        {
            if (Settings.Language == value || !AppSettings.Languages.Contains(value)) return;
            Settings.Language = value;
            OnPropertyChanged();
            // 알림이 먼저 나가야 문구가 새 언어로 만들어진다(App 이 리소스 사전을 바꾼다).
            Commit("Language", () => _text("Status.Language"));
        }
    }

    // --- 시작 프로그램, 창 기억 -----------------------------------------------------------------

    public bool StartWithWindows
    {
        get => _startWithWindows;
        set
        {
            if (_startWithWindows == value) return;
            var error = _setStartup(value);
            if (error is not null)
            {
                _status(string.Format(_text("Status.StartupFailed"), error));
                return;
            }
            _startWithWindows = value;
            OnPropertyChanged();
            _status(_text(value ? "Status.StartupOn" : "Status.StartupOff"));
        }
    }

    /// <summary>등록 상태를 다시 읽는다(작업 관리자에서 바꿨을 수 있다).</summary>
    public void RefreshStartup()
    {
        var actual = _isStartupEnabled();
        if (actual == _startWithWindows) return;
        _startWithWindows = actual;
        OnPropertyChanged(nameof(StartWithWindows));
    }

    public bool RememberWindow
    {
        get => Settings.RememberWindow;
        set
        {
            if (Settings.RememberWindow == value) return;
            Settings.RememberWindow = value;
            // 기억하지 않기로 하면 저장된 자리도 버린다 - 켜면 그때부터 다시 기억한다.
            if (!value) Settings.Window = null;
            OnPropertyChanged();
            Commit("RememberWindow", () => _text(value ? "Status.RememberOn" : "Status.RememberOff"));
        }
    }

    /// <summary>끝낼 때(또는 트레이로 숨길 때) 메인 창의 자리를 적어 둔다. 기억하지 않으면 아무것도 하지 않는다.</summary>
    public void RememberBounds(SavedWindowBounds bounds)
    {
        if (!Settings.RememberWindow || Settings.Window == bounds) return;
        Settings.Window = bounds;
        _save(Settings);
    }

    private void Commit(string property, Func<string> message)
    {
        Changed?.Invoke(property);
        var error = _save(Settings);
        _status(error is null ? message() : string.Format(_text("Status.SettingsSaveFailed"), error));
    }
}
