using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Windows.Data;
using System.Windows.Input;
using WindowResizer.App.Mvvm;
using WindowResizer.Core.Diagnostics;
using WindowResizer.Core.Hotkeys;
using WindowResizer.Core.Overlay;
using WindowResizer.Core.Profiles;
using WindowResizer.Core.Settings;
using WindowResizer.Core.Windowing;

namespace WindowResizer.App.ViewModels;

/// <summary>사이드바 페이지. 순서는 사이드바와 같다(계획 4.2.1).</summary>
public enum AppPage
{
    WindowsAndProfiles,
    Overlay,
    Hotkeys,
    Settings,
    LogAndAbout,
}

/// <summary>
/// 메인 창 상태. 규율은 <c>notes/plans/2026-09-27-s4-main-window-state-and-menu-map.md</c> 2절이다.
///
/// - 선택된 창은 <see cref="SelectedWindow"/> 하나가 소유한다. 목록을 새로 열 때마다 hwnd 로 한 번
///   재검증하고, 없으면 비운다. PyQt5 는 이 값을 8곳에서 따로 다시 정했다.
/// - 프로필 적용은 창 선택을 요구하지 않는다. <b>먼저 목록을 새로 열고</b> 새 목록에서 맞는 창 전부에 적용한다.
/// - 버튼, 메뉴, 키가 같은 명령을 쓴다.
/// - 프로필 문서(<see cref="ProfileDocument"/>)는 이 클래스 하나가 소유한다. <see cref="Profiles"/> 는 그 표시용
///   사본이고, 바꿀 때는 <see cref="Commit"/> 한 곳을 거친다: 바꾸고 -> 저장하고 -> 실패하면 되돌린다.
///   저장에 실패한 변경이 화면에만 남아 "저장된 줄 아는" 상태를 만들지 않는다.
/// </summary>
public sealed class MainViewModel : ObservableObject
{
    private readonly Func<IReadOnlyList<WindowRow>> _enumerateWindows;
    private readonly IWindowOperations _windows;
    private readonly ProfileApplier _applier;
    private readonly ProfileDocument _document;
    private readonly Func<ProfileDocument, string?> _save;
    private readonly IDialogService _dialogs;
    private readonly Func<string, string> _text;
    private readonly Func<double> _now;

    private AppPage _page = AppPage.WindowsAndProfiles;
    private WindowRow? _selectedWindow;
    private ProfileRow? _selectedProfile;
    private string _searchText = "";
    private string _status = "";

    /// <summary>되돌릴 수 있는 마지막 위치 덮어쓰기. 다른 변경이 저장되면 비운다 - 그 뒤로는 되돌리면 남의 변경을 덮는다.</summary>
    private (string Id, WindowConfiguration Before)? _undo;

    /// <param name="enumerateWindows">사용자 창 목록(Infrastructure <c>EnumerateUserWindows</c>).</param>
    /// <param name="document">읽어 온 프로필 문서. 이 뒤로는 이 ViewModel 만 바꾼다.</param>
    /// <param name="save">문서 저장. 성공하면 null, 실패하면 사용자에게 보일 원인.</param>
    /// <param name="text">문자열 리소스 조회. 키 -> 표시 문자열.</param>
    /// <param name="exit">명시적 종료. 메뉴 "종료"(Ctrl+Q)는 트레이로 숨기지 않고 진짜 끝낸다(D-020).</param>
    /// <param name="now">Unix epoch 초. 테스트가 고정한다.</param>
    public MainViewModel(
        Func<IReadOnlyList<WindowRow>> enumerateWindows,
        IWindowOperations windows,
        ProfileDocument document,
        Func<ProfileDocument, string?> save,
        IDialogService dialogs,
        Func<string, string> text,
        Action? exit = null,
        Func<double>? now = null,
        OverlaySettings? overlaySettings = null,
        Func<OverlaySettings, string?>? saveOverlay = null,
        HotkeyServices? hotkeys = null,
        SettingsServices? settings = null,
        AboutInfo? about = null)
    {
        _enumerateWindows = enumerateWindows;
        _windows = windows;
        _applier = new ProfileApplier(windows);
        _document = document;
        _save = save;
        _dialogs = dialogs;
        _text = text;
        _now = now ?? (() => DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0);

        Profiles = new ObservableCollection<ProfileRow>(RowsOf(document));
        WindowsView = CollectionViewSource.GetDefaultView(Windows);
        WindowsView.Filter = MatchesSearch;

        RefreshCommand = new RelayCommand(RefreshWindows);
        // 읽지 못한 프로필은 삭제만 된다(D-022).
        ApplyProfileCommand = new RelayCommand(ApplySelectedProfile, () => SelectedProfile is { IsUnreadable: false });
        NewProfileFromWindowCommand = new RelayCommand(NewProfileFromSelectedWindow, () => SelectedWindow is not null);
        EditProfileCommand = new RelayCommand(EditSelectedProfile, () => SelectedProfile is { IsUnreadable: false });
        DeleteProfileCommand = new RelayCommand(DeleteSelectedProfile, () => SelectedProfile is not null);
        OverwritePositionCommand = new RelayCommand(OverwriteSelectedProfilePosition,
            () => SelectedWindow is not null && SelectedProfile is { IsUnreadable: false });
        UndoCommand = new RelayCommand(Undo, () => CanUndo);
        NavigateCommand = new ParameterCommand<AppPage>(page => Page = page);
        ExitCommand = new RelayCommand(exit ?? (() => { }));

        Activity = new ActivityLog();
        Log = new LogViewModel(Activity, dialogs, text, ShowStatus);
        About = new AboutViewModel(about ?? AboutInfo.Unknown, dialogs, text, ShowStatus);
        Overlay = new OverlayViewModel(overlaySettings ?? new OverlaySettings(), saveOverlay ?? (_ => null), text, message => ShowStatus(message),
            warning: message => ShowStatus(message, LogLevel.Warning));
        SetProfileOverlayCommand = new ParameterCommand<ProfileRow>(row => SetProfileOverlay(row, !row.OverlayEnabled));
        CloseAllOverlaysCommand = new RelayCommand(CloseAllOverlays);

        _hotkeyServices = hotkeys ?? new HotkeyServices();
        Hotkeys = new HotkeysViewModel(this, _hotkeyServices, text);
        ApplyAllProfilesCommand = new RelayCommand(ApplyAllProfiles);

        Settings = new SettingsViewModel(
            settings?.Settings ?? new AppSettings(),
            settings?.Save ?? (_ => null),
            settings?.IsStartupEnabled ?? (() => false),
            settings?.SetStartup ?? (_ => null),
            text, message => ShowStatus(message), warning: message => ShowStatus(message, LogLevel.Warning));
    }

    private readonly HotkeyServices _hotkeyServices;

    /// <summary>설정 페이지(테마, 화면 크기, 언어, 시작 프로그램, 창 기억).</summary>
    public SettingsViewModel Settings { get; }

    /// <summary>
    /// 표시 언어가 바뀌었다. 화면의 고정 문구는 리소스 사전을 바꾸면 따라 바뀌지만, 이 클래스들이 문자열로 만들어 둔 것
    /// (단축키 줄 이름, 동작 콤보, 등록 결과 목록)은 다시 만들어야 한다.
    /// </summary>
    public void RefreshTexts()
    {
        Hotkeys.RefreshTexts();
        Log.RefreshTexts();
        About.RefreshTexts();
    }

    /// <summary>앱이 한 일의 기록(로그 페이지). 상태 줄에 뜬 문구와 잡히지 않은 오류가 쌓인다.</summary>
    public ActivityLog Activity { get; }

    public LogViewModel Log { get; }

    public AboutViewModel About { get; }

    /// <summary>단축키 페이지. 프로필을 바꿔 저장할 때마다 등록을 다시 한다(<see cref="RebuildProfiles"/>).</summary>
    public HotkeysViewModel Hotkeys { get; }

    /// <summary>모든 프로필을 맞는 창 전부에 적용한다. 메뉴, 전체 적용 단축키가 같은 명령을 쓴다.</summary>
    public ICommand ApplyAllProfilesCommand { get; }

    public Profile? FindProfile(string id) => _document.Find(id);

    /// <summary>경고 상자. 사용자가 알아야 하지만 되돌릴 선택은 없는 일(등록하지 못한 단축키 등).</summary>
    public void Warn(string title, string message) => _dialogs?.Warn(title, message);

    /// <summary>지금 문서에서 등록할 프로필 단축키.</summary>
    public HotkeyPlan PlanHotkeys() => HotkeyPlanner.Plan(_document);

    /// <summary>
    /// 프로필의 단축키 스위치와 세트를 바꿔 저장한다(D-022). 첫 세트는 단일 필드에도 적는다 -
    /// PyQt5 편집 창이 그렇게 저장하고, 옛 프로그램이 읽는 자리다.
    /// </summary>
    public bool SaveProfileHotkeys(string profileId, bool enabled, IReadOnlyList<HotkeySet> sets)
    {
        var profile = _document.Find(profileId);
        if (profile is null) return false;

        var saved = Commit(() =>
        {
            profile.HotkeyEnabled = enabled;
            profile.HotkeySets = sets.ToList();
            profile.HotkeyCombination = sets.Count > 0 ? sets[0].Combination : "";
            profile.HotkeyAction = sets.Count > 0 ? sets[0].Action : "apply_profile";
            profile.ModifiedAt = _now();
        }, SelectedProfile?.Id);

        if (saved) Status = string.Format(_text("Status.HotkeysSaved"), profile.Name);
        return saved;
    }

    /// <summary>
    /// 단축키가 눌렸다(UI 스레드). 프로필을 고르지 않고 문서에서 id 로 찾는다 - 등록한 뒤 프로필이 지워졌을 수 있다.
    /// 목록의 선택은 건드리지 않는다.
    /// </summary>
    public void RunHotkey(HotkeyBinding binding)
    {
        if (binding.Action == HotkeyAction.ApplyAllProfiles)
        {
            ApplyAllProfiles();
            return;
        }
        if (binding.Action == HotkeyAction.AlwaysOnTopToggle)
        {
            ToggleForegroundTopmost();
            return;
        }

        var row = Profiles.FirstOrDefault(p => p.Id == binding.ProfileId && !p.IsUnreadable);
        if (row is null)
        {
            Alert(_text("Status.HotkeyProfileGone"));
            return;
        }

        switch (binding.Action)
        {
            case HotkeyAction.ApplyProfile:
                ApplyProfileRow(row, () => SelectedProfile?.Id);
                break;
            case HotkeyAction.AutoApplyToggle:
                if (Commit(() =>
                    {
                        row.Profile.AutoApply = !row.Profile.AutoApply;
                        row.Profile.ModifiedAt = _now();
                    }, SelectedProfile?.Id))
                    Status = string.Format(_text(row.Profile.AutoApply ? "Status.HotkeyAutoApplyOn" : "Status.HotkeyAutoApplyOff"), row.Name);
                break;
            default:
                // 이 앱은 아직 창 잠금과 마우스 제한을 걸지 않는다 - 풀 것이 없다는 사실을 그대로 알린다.
                Status = string.Format(_text("Status.HotkeyNothingToRelease"), row.Name);
                break;
        }
    }

    private void ToggleForegroundTopmost()
    {
        var result = _hotkeyServices.ToggleForegroundTopmost?.Invoke();
        if (result is not { } toggled)
        {
            Alert(_text("Status.HotkeyNoForeground"));
            return;
        }

        var title = string.IsNullOrWhiteSpace(toggled.Title) ? _text("Status.UntitledWindow") : toggled.Title;
        if (!toggled.Succeeded) Alert(string.Format(_text("Status.HotkeyTopmostFailed"), title));
        else Status = string.Format(_text(toggled.Topmost ? "Status.HotkeyTopmostOn" : "Status.HotkeyTopmostOff"), title);
    }

    /// <summary>
    /// 모든 프로필을 맞는 창 전부에 적용한다(PyQt5 <c>auto_apply_profiles</c>). 먼저 목록을 새로 열어
    /// 방금 뜬 창까지 잡는다. 한 창에 프로필 둘이 맞으면 둘 다 적용하고 나중 것이 남는다(PyQt5 와 같다).
    /// </summary>
    public void ApplyAllProfiles()
    {
        RefreshWindows();

        var counts = new List<(Profile Profile, int Applied)>();
        var failed = 0;
        foreach (var (_, profile) in _document.Profiles)
        {
            if (profile.WindowConfig is not { } config) continue;

            var applied = 0;
            foreach (var window in Windows.Where(w => profile.Matches(w.Info)).ToList())
            {
                if (_applier.Apply(window.Handle, config) == ApplyOutcome.Applied) applied++;
                else failed++;
            }
            if (applied > 0) counts.Add((profile, applied));
        }

        var total = counts.Sum(c => c.Applied);
        if (total == 0 && failed == 0)
        {
            Status = _text("Status.AppliedAllNone");
            return;
        }

        RefreshWindows();
        var message = total == 0
            ? string.Format(_text("Status.AppliedAllFailed"), failed)
            : failed == 0
                ? string.Format(_text("Status.AppliedAll"), total)
                : string.Format(_text("Status.AppliedAllWithFailures"), total, failed);

        if (total > 0 && !Commit(() => counts.ForEach(c => c.Profile.RecordApplied(c.Applied, _now())),
                () => SelectedProfile?.Id, clearsUndo: false)) return;
        if (failed > 0) Alert(message);
        else Status = message;
    }

    /// <summary>오버레이 전역 설정. 오버레이 페이지, 메뉴 막대, 트레이가 같은 객체를 본다.</summary>
    public OverlayViewModel Overlay { get; }

    /// <summary>프로필 하나의 오버레이 버튼을 켜고 끈다(행을 넘긴다 - 누른 쪽의 반대 값으로).</summary>
    public ICommand SetProfileOverlayCommand { get; }

    /// <summary>
    /// 모든 오버레이 버튼을 닫는다. PyQt5 와 같이 각 프로필의 사용 여부를 끄고 저장한다 - 무엇을 띄울지는
    /// 프로필 한 곳이 정한다. 화면에서만 닫으면 다음 실행에 되살아나 편집 창의 체크와 어긋난다.
    /// </summary>
    public ICommand CloseAllOverlaysCommand { get; }

    /// <summary>프로필 오버레이 사용 여부를 바꾸고 저장한다. 버튼 창의 닫기(O3)도 이 길로 온다.</summary>
    public void SetProfileOverlay(ProfileRow row, bool enabled)
    {
        if (row.IsUnreadable) return;
        var profile = _document.Find(row.Id);
        if (profile is null) return;

        if (Commit(() =>
            {
                profile.OverlayStyle ??= new OverlayStyle();
                profile.OverlayStyle.Enabled = enabled;
            }, SelectedProfile?.Id))
            Status = string.Format(_text(enabled ? "Status.OverlayProfileOn" : "Status.OverlayProfileOff"), profile.Name);
    }

    /// <summary>
    /// 오버레이 버튼이 누른 프로필을 창 하나에 적용한다. PyQt5 <c>apply_profile(id, window_info)</c> 와 같이
    /// <b>매칭 조건을 보지 않는다</b> - 버튼은 "직전에 쓰던 창에 이 배치를" 이라는 뜻이다. 성공하면 적용 횟수를
    /// 저장한다(되돌리기는 지우지 않는다). 결과는 상태 줄과 반환값(버튼의 성공/실패 색)으로 알린다.
    /// </summary>
    /// <param name="target">대상 창. 없으면(추적 대상이 닫힘) null.</param>
    public bool ApplyProfileToWindow(string profileId, nint? target, string targetTitle)
    {
        var profile = _document.Find(profileId);
        if (profile?.WindowConfig is null)
        {
            Alert(_text("Status.OverlayProfileMissing"));
            return false;
        }
        if (target is not { } hwnd)
        {
            Alert(_text("Status.OverlayNoTarget"));
            return false;
        }

        var title = string.IsNullOrWhiteSpace(targetTitle) ? _text("Status.UntitledWindow") : targetTitle;
        if (_applier.Apply(hwnd, profile.WindowConfig) != ApplyOutcome.Applied)
        {
            Alert(string.Format(_text("Status.OverlayApplyFailed"), title));
            return false;
        }

        if (!Commit(() => profile.RecordApplied(1, _now()), () => SelectedProfile?.Id, clearsUndo: false)) return true;
        Status = string.Format(_text("Status.OverlayApplied"), profile.Name, title);
        return true;
    }

    public void CloseAllOverlays()
    {
        var open = _document.Profiles.Where(p => p.Value.OverlayStyle?.Enabled == true).Select(p => p.Value).ToList();
        if (open.Count == 0)
        {
            Status = _text("Status.OverlayNoneOpen");
            return;
        }

        if (Commit(() => open.ForEach(p => p.OverlayStyle!.Enabled = false), SelectedProfile?.Id))
            Status = _text("Status.OverlayAllClosed");
    }

    /// <summary>시작 시 한 줄 알림(프로필을 백업에서 읽음 등). 창 목록 상태로 곧 덮인다.</summary>
    public void ShowStatus(string message, LogLevel level = LogLevel.Info)
    {
        _nextLevel = level;
        Status = message;
    }

    /// <summary>잡히지 않은 오류를 로그에 오류로 남기고 상태 줄에도 알린다. 예외의 전체 내용(스택 포함)이 로그에 들어간다.</summary>
    public void LogException(Exception exception)
    {
        _nextLevel = LogLevel.Error;
        Status = string.Format(_text("Status.UnhandledError"), exception.GetType().Name, exception.Message);
        Activity.Add(LogLevel.Error, exception.ToString());
    }

    public ObservableCollection<WindowRow> Windows { get; } = new();
    public ICollectionView WindowsView { get; }
    public ObservableCollection<ProfileRow> Profiles { get; }

    public ICommand RefreshCommand { get; }
    public ICommand ApplyProfileCommand { get; }
    public ICommand NewProfileFromWindowCommand { get; }
    public ICommand EditProfileCommand { get; }
    public ICommand DeleteProfileCommand { get; }
    public ICommand OverwritePositionCommand { get; }
    public ICommand UndoCommand { get; }
    public ICommand NavigateCommand { get; }

    /// <summary>상태 줄의 되돌리기 버튼이 보이는가.</summary>
    public bool CanUndo => _undo is not null;
    public ICommand ExitCommand { get; }

    public AppPage Page
    {
        get => _page;
        set
        {
            if (!Set(ref _page, value)) return;
            // 작업 관리자에서 시작 앱을 껐을 수 있다 - 설정 페이지는 열 때마다 Windows 의 실제 등록 상태를 다시 읽는다.
            if (value == AppPage.Settings) Settings.RefreshStartup();
        }
    }

    public WindowRow? SelectedWindow
    {
        get => _selectedWindow;
        set => Set(ref _selectedWindow, value);
    }

    public ProfileRow? SelectedProfile
    {
        get => _selectedProfile;
        set => Set(ref _selectedProfile, value);
    }

    /// <summary>제목이나 프로세스 이름에 들어 있으면 보인다. 대소문자 무시(PyQt5 와 같다).</summary>
    public string SearchText
    {
        get => _searchText;
        set
        {
            if (Set(ref _searchText, value)) WindowsView.Refresh();
        }
    }

    public string Status
    {
        get => _status;
        // 상태 줄에 뜨는 모든 문구가 로그에도 남는다(로그 페이지). 수준은 Alert/ShowStatus 가 정한 것, 아니면 정보다.
        private set
        {
            Activity.Add(_nextLevel, value);
            _nextLevel = LogLevel.Info;
            Set(ref _status, value);
        }
    }

    private LogLevel _nextLevel = LogLevel.Info;

    /// <summary>잘 안 된 일을 상태 줄에 알린다. 로그에는 경고로 남는다.</summary>
    private void Alert(string message)
    {
        _nextLevel = LogLevel.Warning;
        Status = message;
    }

    public int WindowCount => Windows.Count;
    public int ProfileCount => Profiles.Count;

    public void RefreshWindows()
    {
        var previous = SelectedWindow?.Handle;
        var rows = _enumerateWindows();

        Windows.Clear();
        foreach (var row in rows) Windows.Add(row);
        OnPropertyChanged(nameof(WindowCount));

        // 선택은 hwnd 로 한 번만 되살린다. 창이 사라졌으면 비운다.
        SelectedWindow = previous is null ? null : Windows.FirstOrDefault(w => w.Handle == previous);
        Status = string.Format(_text("Status.WindowsFound"), Windows.Count);
    }

    public void ApplySelectedProfile()
    {
        var row = SelectedProfile;
        if (row is null || row.IsUnreadable) return;
        ApplyProfileRow(row, () => row.Id);
    }

    /// <summary>
    /// 프로필 하나를 맞는 창 전부에 적용한다. 버튼, 메뉴, Enter 와 프로필 단축키가 같은 이 길을 쓴다.
    /// <paramref name="selectAfter"/> 는 저장 뒤 목록에서 선택할 프로필 - 단축키는 사용자의 선택을 옮기지 않는다.
    /// </summary>
    private void ApplyProfileRow(ProfileRow row, Func<string?> selectAfter)
    {
        // 새로 뜬 창까지 한 번에 잡으려고 적용 직전에 목록을 새로 연다.
        RefreshWindows();

        var config = row.Profile.WindowConfig;
        var targets = Windows.Where(w => row.Profile.Matches(w.Info)).ToList();
        if (targets.Count == 0 || config is null)
        {
            Alert(string.Format(_text("Status.NoMatch"), row.Name));
            return;
        }

        var applied = targets.Count(w => _applier.Apply(w.Handle, config) == ApplyOutcome.Applied);
        var failed = targets.Count - applied;

        // 옮긴 좌표가 목록에 보이게 다시 연다.
        RefreshWindows();
        var message = failed == 0
            ? string.Format(_text("Status.Applied"), row.Name, applied)
            : string.Format(_text("Status.AppliedWithFailures"), row.Name, applied, failed);

        // 적용 횟수는 창은 이미 옮겼으니 저장 실패가 적용을 되돌리지 않는다. 실패만 알린다.
        // 적용 횟수는 위치를 바꾸지 않으므로 덮어쓰기 되돌리기를 지우지 않는다 - 덮어쓴 뒤 적용해 보고 되돌리는 흐름.
        if (applied > 0 && !Commit(() => row.Profile.RecordApplied(applied, _now()), selectAfter, clearsUndo: false)) return;
        if (failed > 0) Alert(message);
        else Status = message;
    }

    /// <summary>
    /// 선택한 창을 새 프로필로 저장한다(Ctrl+S, D-021). 캡처 규칙은 Core <see cref="WindowCapture"/> 하나다.
    /// 미리 채운 편집 창을 "위치와 크기" 페이지로 열고, 저장을 눌렀을 때만 문서에 넣는다.
    /// </summary>
    public void NewProfileFromSelectedWindow()
    {
        var window = SelectedWindow;
        if (window is null) return;

        var capture = WindowCapture.Capture(_windows, window.Handle);
        if (!capture.Succeeded)
        {
            Alert(string.Format(_text("Status.CaptureRefused"), window.Info.Title, _text("Capture." + capture.Refusal)));
            return;
        }

        var name = _document.UniqueName(Profile.ProgramName(window.Info));
        var editor = CreateEditor(Profile.FromWindow(window.Info, capture.Configuration!, name), null, EditorPage.Position);
        if (!ShowEditor(editor)) return;

        string? id = null;
        if (Commit(() => id = _document.Add(editor.Profile, _now()), () => id))
            Status = string.Format(_text("Status.ProfileCreated"), editor.Profile.Name);
    }

    public void EditSelectedProfile()
    {
        var row = SelectedProfile;
        if (row is null || row.IsUnreadable) return;

        var editor = CreateEditor(ProfileJson.Clone(row.Profile), row.Id, EditorPage.General);
        if (!ShowEditor(editor)) return;

        if (Commit(() => _document.Replace(row.Id, editor.Profile, _now()), row.Id))
            Status = string.Format(_text("Status.ProfileSaved"), editor.Profile.Name);
    }

    public void DeleteSelectedProfile()
    {
        var row = SelectedProfile;
        if (row is null || !_dialogs.ConfirmDelete(row.Name)) return;

        if (Commit(() => _document.Remove(row.Id), (string?)null))
            Status = string.Format(_text("Status.ProfileDeleted"), row.Name);
    }

    /// <summary>
    /// 선택한 창의 지금 위치로 선택한 프로필의 위치와 크기만 바꾼다(D-021 결정 3). 확인을 묻지 않는 대신
    /// 상태 줄에 이전/새 좌표와 되돌리기를 보인다. 캡처 규칙은 새 프로필과 같은 <see cref="WindowCapture"/> 다.
    /// 항상 위, 투명도 같은 나머지 창 설정은 그대로 둔다.
    /// </summary>
    public void OverwriteSelectedProfilePosition()
    {
        var window = SelectedWindow;
        var row = SelectedProfile;
        if (window is null || row is null || row.IsUnreadable) return;

        var capture = WindowCapture.Capture(_windows, window.Handle);
        if (!capture.Succeeded)
        {
            Alert(string.Format(_text("Status.CaptureRefused"), window.Info.Title, _text("Capture." + capture.Refusal)));
            return;
        }

        var before = row.Profile.WindowConfig is null ? null : CloneConfig(row.Profile.WindowConfig);
        var after = before is null ? new WindowConfiguration() : CloneConfig(before);
        var c = capture.Configuration!;
        (after.X, after.Y, after.Width, after.Height, after.IsMaximized, after.IsMinimized) =
            (c.X, c.Y, c.Width, c.Height, c.IsMaximized, false);

        if (!Commit(() => row.Profile.WindowConfig = after, row.Id)) return;

        _undo = before is null ? null : (row.Id, before);
        OnPropertyChanged(nameof(CanUndo));
        Status = string.Format(_text("Status.PositionOverwritten"), row.Name, Describe(before), Describe(after));
    }

    /// <summary>마지막 위치 덮어쓰기를 되돌린다. 되돌리기도 저장이다 - 같은 <see cref="Commit"/> 을 거친다.</summary>
    public void Undo()
    {
        if (_undo is not { } undo) return;
        var profile = _document.Find(undo.Id);
        if (profile is null) return;

        if (Commit(() => profile.WindowConfig = undo.Before, undo.Id))
        {
            Status = string.Format(_text("Status.PositionRestored"), profile.Name, Describe(undo.Before));
            return;
        }

        // 저장이 실패했으면 아무것도 안 바뀌었다. 다시 시도할 수 있게 남긴다.
        _undo = undo;
        OnPropertyChanged(nameof(CanUndo));
    }

    private static WindowConfiguration CloneConfig(WindowConfiguration c) => new()
    {
        X = c.X, Y = c.Y, Width = c.Width, Height = c.Height,
        IsMaximized = c.IsMaximized, IsMinimized = c.IsMinimized, MonitorIndex = c.MonitorIndex,
        ZOrder = c.ZOrder, Opacity = c.Opacity, AlwaysOnTop = c.AlwaysOnTop,
    };

    private string Describe(WindowConfiguration? c) =>
        c is null ? "-" : $"{c.X}, {c.Y}, {c.Width}x{c.Height}" + (c.IsMaximized ? " " + _text("Status.MaximizedMark") : "");

    /// <summary>편집 창을 연다. 창에 단축키 입력 칸이 있어서, 열려 있는 동안은 전역 단축키 등록을 풀어 둔다.</summary>
    private bool ShowEditor(ProfileEditorViewModel editor)
    {
        Hotkeys.BeginDialog();
        try
        {
            return _dialogs.ShowEditor(editor);
        }
        finally
        {
            Hotkeys.EndDialog();
        }
    }

    public ProfileEditorViewModel CreateEditor(Profile working, string? id, EditorPage page) =>
        new(working, page,
            name => _document.Profiles.Any(p => p.Key != id &&
                string.Equals(p.Value.Name.Trim(), name.Trim(), StringComparison.OrdinalIgnoreCase)),
            _enumerateWindows, _windows, _dialogs, _text);

    private bool Commit(Action change, string? selectId) => Commit(change, () => selectId);

    /// <summary>
    /// 문서를 바꾸는 유일한 길. 바꾸기 전 문서를 직렬화해 두고, 저장이 실패하면 그 상태로 되돌린다.
    /// 성공하든 실패하든 목록은 문서에서 다시 만든다 - 행이 들고 있는 값이 문서와 어긋나지 않게.
    /// </summary>
    private bool Commit(Action change, Func<string?> selectId, bool clearsUndo = true)
    {
        var before = ProfileJson.Serialize(_document);
        // 읽지 못한 프로필은 불변 레코드라 목록을 그대로 떠 둔다. 직렬화본을 다시 읽어 되살리면 판정을 한 번 더
        // 하게 되어, 판정이 달라지면 "읽을 수 없음" 줄이 정상 프로필로 둔갑한다.
        var unreadableBefore = _document.Unreadable.ToList();

        // 되돌리기는 바로 다음 변경 전까지만 유효하다. 덮어쓰기 자신은 저장 뒤에 다시 채운다.
        if (clearsUndo)
        {
            _undo = null;
            OnPropertyChanged(nameof(CanUndo));
        }
        change();

        var error = _save(_document);
        if (error is not null)
        {
            var restored = ProfileJson.Parse(before).Document;
            var unreadableIds = unreadableBefore.Select(u => u.Id).ToHashSet();
            _document.Profiles.Clear();
            _document.Profiles.AddRange(restored.Profiles.Where(p => !unreadableIds.Contains(p.Key)));
            _document.Unreadable.Clear();
            _document.Unreadable.AddRange(unreadableBefore);
            RebuildProfiles(SelectedProfile?.Id);
            Alert(string.Format(_text("Status.SaveFailed"), error));
            return false;
        }

        RebuildProfiles(selectId());
        return true;
    }

    private void RebuildProfiles(string? selectId)
    {
        Profiles.Clear();
        foreach (var row in RowsOf(_document)) Profiles.Add(row);
        OnPropertyChanged(nameof(ProfileCount));
        SelectedProfile = selectId is null ? null : Profiles.FirstOrDefault(p => p.Id == selectId);
        // 단축키는 프로필 문서가 정한다 - 저장, 삭제, 되돌림 어느 쪽이든 문서가 바뀌었으면 다시 맞춘다.
        Hotkeys.Sync();
    }

    /// <summary>읽은 프로필 다음에 읽지 못한 프로필(흐린 줄). 파일에 쓰는 순서와 같다.</summary>
    private static IEnumerable<ProfileRow> RowsOf(ProfileDocument document) =>
        document.Profiles.Select(p => new ProfileRow(p.Key, p.Value))
            .Concat(document.Unreadable.Select(ProfileRow.ForUnreadable));

    private bool MatchesSearch(object item)
    {
        if (string.IsNullOrWhiteSpace(_searchText)) return true;
        var row = (WindowRow)item;
        return row.Info.Title.Contains(_searchText, StringComparison.OrdinalIgnoreCase)
            || row.Info.ProcessName.Contains(_searchText, StringComparison.OrdinalIgnoreCase);
    }
}

/// <summary>매개변수 하나를 받는 명령. 사이드바 항목이 페이지 값을 넘긴다.</summary>
public sealed class ParameterCommand<T>(Action<T> execute) : ICommand
{
    public event EventHandler? CanExecuteChanged { add { } remove { } }

    public bool CanExecute(object? parameter) => parameter is T;

    public void Execute(object? parameter)
    {
        if (parameter is T value) execute(value);
    }
}
