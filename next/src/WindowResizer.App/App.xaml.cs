using System.Windows;
using WindowResizer.App.Theming;
using WindowResizer.App.ViewModels;
using WindowResizer.Core.Settings;
using WindowResizer.Infrastructure.Persistence;
using WindowResizer.Infrastructure.Settings;
using WindowResizer.Infrastructure.Windowing;

namespace WindowResizer.App;

/// <summary>
/// 조합 루트. Core 와 Infrastructure 부품을 여기서만 엮는다.
///
/// 실행 인자:
///   <c>--profiles-dir &lt;폴더&gt;</c>  프로필 폴더를 바꾼다. 기본은 실행 파일 옆 <c>profiles</c>(D-019).
///   개발 빌드는 <c>next\...\bin</c> 에서 뜨므로, 실사용 프로필을 보려면 <c>C:\app\profiles</c> 를 넘긴다.
///   S4b 부터 이 폴더에 <b>쓴다</b>(적용 횟수, 편집, 삭제). 개발 중에는 실사용 폴더가 아니라 사본을 넘긴다.
///   <c>--overlay-key &lt;HKCU 아래 경로&gt;</c>  오버레이 설정 키를 바꾼다(PyQt5 키에서 가져오지도 않는다).
///   라이브 검증이 사용자 설정을 건드리지 않게 쓴다.
///   <c>--hotkey-key &lt;HKCU 아래 경로&gt;</c>  전체 적용 단축키 키를 바꾼다(PyQt5 파일에서 가져오지도 않는다). 같은 이유다.
///   <c>--settings-key &lt;HKCU 아래 경로&gt;</c>  앱 설정(테마, 화면 크기, 언어, 창 기억) 키를 바꾼다(PyQt5 키에서 가져오지도 않는다).
///   <c>--run-key &lt;HKCU 아래 경로&gt;</c>  "Windows 시작 때 자동 실행"이 쓰는 Run 키를 바꾼다. 실제 시작 목록을 건드리지 않게.
///   <c>--minimized</c>  창을 열지 않고 트레이로만 뜬다(시작 프로그램으로 등록되면 이 인자가 붙는다).
/// </summary>
public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        // 이전 실행이 커서를 가둔 채 죽었으면 푼다(S3c 실측: Windows 는 풀어 주지 않는다).
        CursorClip.ReleaseStale();

        // 언어, 테마, 배율은 창과 문구를 만들기 전에 정해 둔다 - 첫 화면이 기본값으로 한 번 그려졌다 바뀌지 않게.
        var settingsKey = ArgValue(e.Args, "--settings-key");
        var settingsStore = settingsKey is null ? new AppSettingsStore() : new AppSettingsStore(settingsKey, legacyThemeKeyPath: null, legacyScaleKeyPath: null);
        _settings = settingsStore.Load();
        ApplyLanguage(_settings.Language);
        ApplyTheme();
        UiScale.Set(_settings.ScaleFactor);
        Microsoft.Win32.SystemEvents.UserPreferenceChanged += OnUserPreferenceChanged;

        var runKey = ArgValue(e.Args, "--run-key");
        var startup = runKey is null ? new StartupRegistration() : new StartupRegistration(runKey);

        var store = new ProfileStore(ProfilesDirectory(e.Args));
        var loaded = store.Load();
        var windows = new Win32Windows();
        var overlayKey = ArgValue(e.Args, "--overlay-key");
        var overlayStore = overlayKey is null ? new OverlaySettingsStore() : new OverlaySettingsStore(overlayKey, legacyKeyPath: null);

        var hotkeyKey = ArgValue(e.Args, "--hotkey-key");
        var hotkeyStore = hotkeyKey is null ? new HotkeySettingsStore() : new HotkeySettingsStore(hotkeyKey, legacyFilePath: null);
        _hotkeys = new HotkeyRegistrar();

        var viewModel = new MainViewModel(
            () => windows.EnumerateUserWindows()
                .Select(w => new WindowRow(w.Handle, w.Info, w.ProcessId, w.Rect, w.IsMaximized, w.IsMinimized))
                .ToList(),
            windows,
            loaded.Document,
            document => Save(store, loaded.Source, document),
            new DialogService(Text),
            Text,
            Quit,
            overlaySettings: overlayStore.Load(),
            saveOverlay: settings => overlayStore.TrySave(settings, out var error) ? null : error!.Message,
            hotkeys: new HotkeyServices(
                _hotkeys,
                hotkeyStore.Load(),
                hotkey => hotkeyStore.TrySave(hotkey, out var error) ? null : error!.Message,
                Win32Windows.ToggleForegroundTopmost,
                // 등록기는 자기 스레드에서 알린다. 화면 상태는 UI 스레드에서만 만진다.
                action => Dispatcher.BeginInvoke(action)),
            settings: new SettingsServices(
                _settings,
                settings => settingsStore.TrySave(settings, out var error) ? null : error!.Message,
                startup.IsEnabled,
                enabled => startup.Set(enabled, Environment.ProcessPath ?? "")),
            about: new AboutInfo(
                AppInfo.DisplayVersion,
                System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription,
                IsAdministrator(),
                Environment.ProcessPath ?? "",
                System.IO.Path.GetFullPath(ProfilesDirectory(e.Args)),
                settingsStore.KeyPath, overlayStore.KeyPath, hotkeyStore.KeyPath));
        _viewModel = viewModel;
        viewModel.ShowStatus(string.Format(Text("Log.Started"), AppInfo.DisplayVersion));
        HookUnhandledExceptions();
        viewModel.Settings.Changed += OnSettingChanged;

        viewModel.Hotkeys.Sync();
        viewModel.RefreshWindows();
        var notice = LoadNotice(loaded);
        if (notice is not null) viewModel.ShowStatus(notice, Core.Diagnostics.LogLevel.Warning);

        var window = new MainWindow { DataContext = viewModel };
        MainWindow = window;
        RestoreBounds(window);
        MainWindow.Closing += OnMainWindowClosing;
        _tray = new TrayIcon(Text, ShowMainWindow, Quit, viewModel.Overlay, viewModel.CloseAllOverlays);
        // 시작 프로그램으로 뜬 것이면 창 없이 트레이로만 뜬다.
        if (!e.Args.Contains(StartupRegistration.MinimizedArgument)) MainWindow.Show();

        // 오버레이 버튼(O3). 직전 창 추적은 창 이벤트 감시기를 따른다(D-023) - 이 프로세스의 창은 감시기가 거른다.
        _windowEvents = new WindowEventWatcher();
        _foreground = new ForegroundTracker(_windowEvents);
        _overlays = new Overlay.OverlayController(viewModel, _foreground, Text);
        // 버튼의 "새로 만들기"와 "덮어쓰기"가 잡을 창은 직전에 쓰던 다른 프로그램 창이다.
        viewModel.OverlayTarget = () => _foreground.Target;
        viewModel.WindowTitle = hwnd => Infrastructure.Windowing.Win32Windows.DescribeWindow(hwnd).Title;
    }

    private AppSettings _settings = new();
    private MainViewModel? _viewModel;
    private HotkeyRegistrar? _hotkeys;
    private TrayIcon? _tray;
    private WindowEventWatcher? _windowEvents;
    private ForegroundTracker? _foreground;
    private Overlay.OverlayController? _overlays;
    private bool _quitting;

    /// <summary>
    /// 창 닫기(X, Alt+F4)는 트레이로 숨기기만 한다(D-020). 진짜 종료는 <see cref="Quit"/> 하나다 -
    /// 메뉴 "종료"(Ctrl+Q)와 트레이 "프로그램 종료"가 같은 경로다. PyQt5 는 메뉴 "종료"도 숨기기만 했다.
    /// </summary>
    private void OnMainWindowClosing(object? sender, System.ComponentModel.CancelEventArgs e)
    {
        // 숨기든 끝내든 이 창이 마지막으로 있던 자리를 적어 둔다.
        RememberBounds(MainWindow!);
        if (_quitting || _tray is null) return;
        e.Cancel = true;
        MainWindow!.Hide();
        _tray.NotifyHiddenOnce();
    }

    /// <summary>
    /// 잡히지 않은 오류를 로그 페이지에 오류로 남긴다. 화면 스레드의 오류는 <b>처리한 것으로 표시해</b> 앱을 살려 둔다 -
    /// 트레이에 상주하는 앱이 화면 한 곳의 예외로 통째로 사라지지 않게(대신 상태 줄과 로그에 남는다). 다른 스레드의
    /// 오류는 런타임이 프로세스를 끝내므로 끝나기 전에 로그에 적기만 한다.
    /// </summary>
    private void HookUnhandledExceptions()
    {
        DispatcherUnhandledException += (_, e) =>
        {
            _viewModel?.LogException(e.Exception);
            e.Handled = true;
        };
        AppDomain.CurrentDomain.UnhandledException += (_, e) =>
        {
            if (e.ExceptionObject is Exception exception) _viewModel?.LogException(exception);
        };
        TaskScheduler.UnobservedTaskException += (_, e) =>
        {
            Dispatcher.BeginInvoke(() => _viewModel?.LogException(e.Exception));
            e.SetObserved();
        };
    }

    private static bool IsAdministrator()
    {
        using var identity = System.Security.Principal.WindowsIdentity.GetCurrent();
        return new System.Security.Principal.WindowsPrincipal(identity).IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator);
    }

    /// <summary>설정 페이지에서 무언가 바뀌었다. 저장은 끝났고 여기서는 실제 화면에 적용만 한다.</summary>
    private void OnSettingChanged(string property)
    {
        switch (property)
        {
            case "Theme":
                ApplyTheme();
                break;
            case "AppliedScale":
                UiScale.Set(_settings.ScaleFactor);
                break;
            case "Language":
                ApplyLanguage(_settings.Language);
                _viewModel?.RefreshTexts();
                _tray?.RefreshTexts();
                break;
        }
    }

    /// <summary>설정과 Windows 의 현재 모드로 색을 정한다. 이미 그 모드면 브러시를 다시 만들지 않는다.</summary>
    private void ApplyTheme()
    {
        var mode = Theme.Resolve(_settings.Theme);
        if (mode != Theme.Current || !_themeApplied)
        {
            Theme.Apply(Resources, mode);
            _themeApplied = true;
        }
    }

    private bool _themeApplied;

    /// <summary>Windows 앱 모드나 고대비가 바뀌었다(다른 스레드에서 온다). "시스템 따르기"이거나 고대비일 때만 뜻이 있다.</summary>
    private void OnUserPreferenceChanged(object sender, Microsoft.Win32.UserPreferenceChangedEventArgs e) =>
        Dispatcher.BeginInvoke(ApplyTheme);

    /// <summary>
    /// 문구 사전을 바꿔 끼운다. XAML 은 전부 <c>DynamicResource</c> 라 열려 있는 창도 바로 따라 바뀐다.
    /// 모르는 언어는 <see cref="AppSettings"/> 가 이미 기본으로 돌려 놓았다.
    /// </summary>
    private void ApplyLanguage(string code)
    {
        var next = new ResourceDictionary { Source = new Uri($"Resources/Strings.{code}.xaml", UriKind.Relative) };
        var merged = Resources.MergedDictionaries;
        var index = -1;
        for (var i = 0; i < merged.Count; i++)
            if (merged[i].Source?.OriginalString.Contains("Strings.", StringComparison.Ordinal) == true) index = i;
        if (index >= 0) merged[index] = next;
        else merged.Insert(0, next);
    }

    /// <summary>
    /// 기억한 창 자리로 연다. 모니터를 뺐거나 해상도가 바뀌었으면 보이는 곳으로 옮긴다.
    /// 저장한 값은 그때의 논리 단위(DIP)라 Windows 배율이 바뀌면 물리 크기는 달라지지만 화면 안에는 있다.
    /// </summary>
    private void RestoreBounds(Window window)
    {
        if (!_settings.RememberWindow || _settings.Window is not { } saved) return;

        var fit = saved.Fit(
            (int)SystemParameters.VirtualScreenLeft, (int)SystemParameters.VirtualScreenTop,
            (int)SystemParameters.VirtualScreenWidth, (int)SystemParameters.VirtualScreenHeight,
            (int)Math.Ceiling(window.MinWidth), (int)Math.Ceiling(window.MinHeight));
        window.WindowStartupLocation = WindowStartupLocation.Manual;
        window.Left = fit.Left;
        window.Top = fit.Top;
        window.Width = fit.Width;
        window.Height = fit.Height;
        if (fit.Maximized) window.WindowState = WindowState.Maximized;
    }

    private void RememberBounds(Window window)
    {
        // 한 번도 열리지 않은 창(--minimized)의 자리는 우리가 정한 값이 아니다.
        if (!window.IsLoaded || _viewModel is null) return;
        var bounds = window.WindowState == WindowState.Normal
            ? new Rect(window.Left, window.Top, window.Width, window.Height)
            : window.RestoreBounds;
        if (bounds.IsEmpty || double.IsNaN(bounds.Width)) return;
        _viewModel.Settings.RememberBounds(new SavedWindowBounds(
            (int)Math.Round(bounds.Left), (int)Math.Round(bounds.Top),
            (int)Math.Round(bounds.Width), (int)Math.Round(bounds.Height),
            window.WindowState == WindowState.Maximized));
    }

    private void ShowMainWindow()
    {
        var window = MainWindow!;
        window.Show();
        if (window.WindowState == WindowState.Minimized) window.WindowState = WindowState.Normal;
        window.Activate();
    }

    private void Quit()
    {
        _quitting = true;
        ReleaseResources();
        Shutdown();
    }

    /// <summary>전역 단축키, 트레이 아이콘, 오버레이 창, 창 이벤트 훅을 푼다. 두 번 불러도 된다.</summary>
    private void ReleaseResources()
    {
        Microsoft.Win32.SystemEvents.UserPreferenceChanged -= OnUserPreferenceChanged;
        _hotkeys?.Dispose();
        _hotkeys = null;
        _tray?.Dispose();
        _tray = null;
        _overlays?.Dispose();
        _overlays = null;
        _foreground?.Dispose();
        _foreground = null;
        _windowEvents?.Dispose();
        _windowEvents = null;
    }

    /// <summary>로그오프나 종료 때는 숨기지 말고 끝낸다. 숨기려고 닫기를 취소하면 Windows 종료를 막는다.</summary>
    protected override void OnSessionEnding(SessionEndingCancelEventArgs e)
    {
        _quitting = true;
        base.OnSessionEnding(e);
    }

    protected override void OnExit(ExitEventArgs e)
    {
        ReleaseResources();
        base.OnExit(e);
    }

    private string Text(string key) => TryFindResource(key) as string ?? key;

    /// <summary>
    /// 본 파일과 백업을 둘 다 못 읽었으면 쓰지 않는다. 빈 문서를 저장하면 사용자의 깨진(그러나 고칠 수 있는)
    /// 파일이 빈 파일로 바뀌고, 백업마저 그 깨진 파일로 밀린다.
    /// </summary>
    private string? Save(ProfileStore store, ProfileSource source, Core.Profiles.ProfileDocument document)
    {
        if (source == ProfileSource.Unreadable) return Text("Status.ReadOnlyProfiles");
        return store.TrySave(document, out var error) ? null : error!.Message;
    }

    private string? LoadNotice(ProfileStoreLoad loaded) => loaded.Source switch
    {
        ProfileSource.Backup => Text("Status.ProfilesFromBackup"),
        ProfileSource.Unreadable => string.Format(Text("Status.ProfilesUnreadable"), string.Join("; ", loaded.FileErrors)),
        _ when loaded.ProfileErrors.Count > 0 => string.Format(Text("Status.ProfilesSkipped"), loaded.ProfileErrors.Count),
        _ => null,
    };

    private static string ProfilesDirectory(string[] args) => ArgValue(args, "--profiles-dir") ?? ProfileStore.DefaultDirectory;

    private static string? ArgValue(string[] args, string name)
    {
        var index = Array.IndexOf(args, name);
        return index >= 0 && index + 1 < args.Length ? args[index + 1] : null;
    }
}
