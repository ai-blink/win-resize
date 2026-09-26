using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Windows.Data;
using System.Windows.Input;
using WindowResizer.App.Mvvm;
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
/// - 버튼, 메뉴, Enter 가 같은 <see cref="ApplyProfileCommand"/> 를 쓴다.
///
/// 이 슬라이스는 프로필 파일을 읽기만 한다. 적용 횟수 갱신과 저장은 편집/삭제와 함께 들어온다.
/// </summary>
public sealed class MainViewModel : ObservableObject
{
    private readonly Func<IReadOnlyList<WindowRow>> _enumerateWindows;
    private readonly ProfileApplier _applier;
    private readonly Func<string, string> _text;

    private AppPage _page = AppPage.WindowsAndProfiles;
    private WindowRow? _selectedWindow;
    private ProfileRow? _selectedProfile;
    private string _searchText = "";
    private string _status = "";

    /// <param name="enumerateWindows">사용자 창 목록(Infrastructure <c>EnumerateUserWindows</c>).</param>
    /// <param name="text">문자열 리소스 조회. 키 -> 표시 문자열.</param>
    /// <param name="exit">명시적 종료. 메뉴 "종료"(Ctrl+Q)는 트레이로 숨기지 않고 진짜 끝낸다(D-020).</param>
    public MainViewModel(
        Func<IReadOnlyList<WindowRow>> enumerateWindows,
        IWindowOperations windows,
        IEnumerable<ProfileRow> profiles,
        Func<string, string> text,
        Action? exit = null)
    {
        _enumerateWindows = enumerateWindows;
        _applier = new ProfileApplier(windows);
        _text = text;

        Profiles = new ObservableCollection<ProfileRow>(profiles);
        WindowsView = CollectionViewSource.GetDefaultView(Windows);
        WindowsView.Filter = MatchesSearch;

        RefreshCommand = new RelayCommand(RefreshWindows);
        ApplyProfileCommand = new RelayCommand(ApplySelectedProfile, () => SelectedProfile is not null);
        NavigateCommand = new ParameterCommand<AppPage>(page => Page = page);
        ExitCommand = new RelayCommand(exit ?? (() => { }));
    }

    /// <summary>시작 시 한 줄 알림(프로필을 백업에서 읽음 등). 창 목록 상태로 곧 덮인다.</summary>
    public void ShowStatus(string message) => Status = message;

    public ObservableCollection<WindowRow> Windows { get; } = new();
    public ICollectionView WindowsView { get; }
    public ObservableCollection<ProfileRow> Profiles { get; }

    public ICommand RefreshCommand { get; }
    public ICommand ApplyProfileCommand { get; }
    public ICommand NavigateCommand { get; }
    public ICommand ExitCommand { get; }

    public AppPage Page
    {
        get => _page;
        set => Set(ref _page, value);
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
        private set => Set(ref _status, value);
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
        if (row is null) return;

        // 새로 뜬 창까지 한 번에 잡으려고 적용 직전에 목록을 새로 연다.
        RefreshWindows();

        var config = row.Profile.WindowConfig;
        var targets = Windows.Where(w => row.Profile.Matches(w.Info)).ToList();
        if (targets.Count == 0 || config is null)
        {
            Status = string.Format(_text("Status.NoMatch"), row.Name);
            return;
        }

        var applied = targets.Count(w => _applier.Apply(w.Handle, config) == ApplyOutcome.Applied);
        var failed = targets.Count - applied;

        // 옮긴 좌표가 목록에 보이게 다시 연다.
        RefreshWindows();
        Status = failed == 0
            ? string.Format(_text("Status.Applied"), row.Name, applied)
            : string.Format(_text("Status.AppliedWithFailures"), row.Name, applied, failed);
    }

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
