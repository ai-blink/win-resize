using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Threading;
using WindowResizer.Core.Overlay;
using WindowResizer.Core.Profiles;
using WindowResizer.Infrastructure.Windowing;

namespace WindowResizer.App.Overlay;

/// <summary>
/// 프로필 하나를 직전에 쓰던 창에 적용하는 떠 있는 버튼(PyQt5 <c>OverlayButton</c>).
///
/// 마우스 규칙은 Core <see cref="OverlayGesture"/> 가, 적용은 <see cref="OverlayController"/> 가 한다. 이 창은
/// 그리기와 이벤트 전달만 한다. 좌표는 전부 물리 픽셀이고 Win32 로 옮긴다 - WPF Left/Top(DIP)을 쓰면 배율이 다른
/// 모니터에서 저장한 자리와 어긋난다.
/// </summary>
public partial class OverlayButtonWindow : Window
{
    /// <summary>적용 결과 색을 보여 주는 시간(PyQt5 FEEDBACK_DURATION_MS).</summary>
    private static readonly TimeSpan FeedbackDuration = TimeSpan.FromMilliseconds(900);

    private readonly OverlayGesture _gesture = new();
    private readonly DispatcherTimer _dwellTimer = new() { Interval = TimeSpan.FromMilliseconds(33) };
    private readonly DispatcherTimer _feedbackTimer = new() { Interval = FeedbackDuration };
    private readonly Stopwatch _dwellClock = new();
    private readonly Func<string, string> _text;

    private OverlayStyle _style = new();
    private string _profileName = "";
    private bool _dwellMode;
    private int _dwellMs = OverlaySettings.DefaultDwellMs;
    private bool? _feedback;   // null 평소, true 성공, false 실패

    public OverlayButtonWindow(string profileId, Func<string, string> text)
    {
        ProfileId = profileId;
        _text = text;
        InitializeComponent();

        _dwellTimer.Tick += OnDwellTick;
        _feedbackTimer.Tick += (_, _) => { _feedbackTimer.Stop(); _feedback = null; Render(); };
        SourceInitialized += (_, _) => Handle = new WindowInteropHelper(this).Handle;
        SourceInitialized += (_, _) =>
        {
            IsNoActivate = Win32Windows.MakeOverlayWindow(Handle);
            HwndSource.FromHwnd(Handle)?.AddHook(Win32Windows.NoActivateHook);
        };
        BuildMenu(null);

        MouseEnter += (_, _) => { _gesture.Enter(_dwellMode); SyncDwellTimer(); Render(); };
        MouseLeave += (_, _) => { _gesture.Leave(); SyncDwellTimer(); Render(); };
        MouseLeftButtonDown += OnPress;
        MouseMove += OnMove;
        MouseLeftButtonUp += OnRelease;
    }

    public string ProfileId { get; }

    public nint Handle { get; private set; }

    /// <summary>활성화 방지 스타일이 실제로 걸렸는가. 걸리지 않았으면 이 버튼을 누르는 순간 대상이 바뀐다.</summary>
    public bool IsNoActivate { get; private set; }

    /// <summary>클릭하거나 드웰이 찼다.</summary>
    public event Action<OverlayButtonWindow>? Triggered;

    /// <summary>드래그를 마쳤다. 인자는 새 왼쪽 위(물리 픽셀).</summary>
    public event Action<OverlayButtonWindow, ScreenPoint>? Moved;

    /// <summary>우클릭 "이 버튼 삭제".</summary>
    public event Action<OverlayButtonWindow>? DeleteRequested;

    /// <summary>우클릭 "지금 창의 위치로 덮어쓰기".</summary>
    public event Action<OverlayButtonWindow>? OverwriteRequested;

    /// <summary>우클릭 "복제".</summary>
    public event Action<OverlayButtonWindow>? DuplicateRequested;

    /// <summary>
    /// 생김새와 발동 설정을 반영한다. 위치는 그대로 둔다. 발동 방식은 프로필이 정했으면 그쪽이 전역을 이긴다
    /// (<see cref="OverlayStyle.ResolvedActivation"/>).
    /// </summary>
    public void Configure(string profileName, OverlayStyle style, OverlaySettings global)
    {
        _profileName = profileName;
        _style = style;
        // 화면에는 안 보이지만(제목 줄 없음, 도구 창) 자동화와 접근성 도구가 이 버튼을 찾는 이름이다.
        Title = "WindowResizer overlay: " + profileName;
        System.Windows.Automation.AutomationProperties.SetName(this, Title);
        var dwellMode = style.ResolvedActivation(global.Activation == OverlayActivation.Dwell ? "dwell" : "click") == "dwell";
        var dwellMs = style.ResolvedDwellMs(global.DwellMs);
        if (dwellMode != _dwellMode || dwellMs != _dwellMs)
        {
            _gesture.CancelDwell();
            _dwellMode = dwellMode;
            _dwellMs = dwellMs;
            SyncDwellTimer();
        }
        _gesture.Locked = global.Locked;

        Width = style.Width;
        Height = style.Height;
        ToolTip = string.Format(_text(_dwellMode ? "Overlay.Button.TipDwell" : "Overlay.Button.TipClick"),
                      _dwellMs / 1000.0, profileName)
                  + Environment.NewLine
                  + _text(global.Locked ? "Overlay.Button.TipLocked" : "Overlay.Button.TipDrag");
        Render();
    }

    /// <summary>적용 결과를 0.9초 동안 색으로 보인다. 성공과 실패는 프로필 색에 묻히지 않게 고정 색이다.</summary>
    public void ShowFeedback(bool success)
    {
        _feedback = success;
        _feedbackTimer.Stop();
        _feedbackTimer.Start();
        Render();
    }

    public double DwellProgress => _gesture.Progress(_dwellMs);

    private void OnPress(object sender, MouseButtonEventArgs e)
    {
        var cursor = Win32Windows.GetCursorPosition();
        var rect = new Win32Windows().GetRect(Handle);
        if (rect is null) return;
        _gesture.Press(new ScreenPoint(cursor.X, cursor.Y), new ScreenPoint(rect.Value.X, rect.Value.Y));
        SyncDwellTimer();
        CaptureMouse();
        e.Handled = true;
    }

    private void OnMove(object sender, MouseEventArgs e)
    {
        if (!IsMouseCaptured) return;
        var cursor = Win32Windows.GetCursorPosition();
        if (_gesture.Move(new ScreenPoint(cursor.X, cursor.Y)) is { } to) Win32Windows.MoveTo(Handle, to.X, to.Y);
    }

    private void OnRelease(object sender, MouseButtonEventArgs e)
    {
        if (!IsMouseCaptured) return;
        ReleaseMouseCapture();
        var result = _gesture.Release(_dwellMode);
        SyncDwellTimer();
        e.Handled = true;

        if (result == GestureRelease.DragEnded && new Win32Windows().GetRect(Handle) is { } rect)
            Moved?.Invoke(this, new ScreenPoint(rect.X, rect.Y));
        else if (result == GestureRelease.Click && !_dwellMode)
            Triggered?.Invoke(this);
    }

    /// <summary>우클릭 "속성...".</summary>
    public event Action<OverlayButtonWindow>? EditRequested;

    /// <summary>우클릭 메뉴(렌더 스모크 테스트가 항목과 클릭을 확인한다).</summary>
    public ContextMenu ButtonMenu => Menu;

    /// <summary>우클릭 메뉴의 위치 줄을 다시 만든다. 버튼의 자리가 바뀔 때마다 부른다.</summary>
    public void SetInfo(string position) => BuildMenu(position);

    /// <summary>
    /// 머리글(프로필 이름, 굵게)과 정보 줄은 항목이 아니라 글자 조각이다 - 비활성 항목은 회색이 되고 마우스를 올리면
    /// 강조되는데, 이 줄들은 누를 수 있는 것이 아니다.
    /// </summary>
    private void BuildMenu(string? position)
    {
        Menu.Items.Clear();
        if (position is not null)
        {
            Menu.Items.Add(InfoText(_profileName, bold: true));
            Menu.Items.Add(InfoText(position));
            Menu.Items.Add(new Separator());
        }
        Menu.Items.Add(Item("Overlay.Menu.Properties", () => EditRequested?.Invoke(this), position is not null));
        Menu.Items.Add(Item("Overlay.Menu.Duplicate", () => DuplicateRequested?.Invoke(this), position is not null));
        // 안전한 항목(속성, 복제) 아래로 기존 값을 바꾸거나 지우는 항목을 나눠 실수로 누르지 않게 한다.
        Menu.Items.Add(new Separator());
        Menu.Items.Add(Item("Overlay.Menu.Overwrite", () => OverwriteRequested?.Invoke(this), position is not null));
        Menu.Items.Add(Item("Overlay.Menu.Delete", () => DeleteRequested?.Invoke(this), true));
    }

    private MenuItem Item(string key, Action click, bool enabled)
    {
        var item = new MenuItem { Header = _text(key), IsEnabled = enabled };
        item.Click += (_, _) => click();
        return item;
    }

    private static TextBlock InfoText(string value, bool bold = false) => new()
    {
        Text = value,
        Margin = new Thickness(14, 3, 14, 3),
        MaxWidth = 360,
        TextWrapping = TextWrapping.Wrap,
        FontWeight = bold ? FontWeights.Bold : FontWeights.Normal,
        Opacity = bold ? 1.0 : 0.75,
        IsHitTestVisible = false,
    };

    private void SyncDwellTimer()
    {
        if (_gesture.IsDwelling && !_dwellTimer.IsEnabled)
        {
            _dwellClock.Restart();
            _dwellTimer.Start();
        }
        else if (!_gesture.IsDwelling && _dwellTimer.IsEnabled)
        {
            _dwellTimer.Stop();
            Render();
        }
    }

    /// <summary>경과는 타이머 주기를 더하지 않고 단조 시계로 잰다 - WPF 타이머는 15.6ms 격자로 늦게 온다.</summary>
    private void OnDwellTick(object? sender, EventArgs e)
    {
        var elapsed = _dwellClock.Elapsed.TotalMilliseconds;
        _dwellClock.Restart();
        if (_gesture.Tick(elapsed, _dwellMs))
        {
            SyncDwellTimer();
            Triggered?.Invoke(this);
            return;
        }
        Render();
    }

    private void Render() =>
        FaceView.Draw(_style, _profileName, _gesture.Hovered, DwellProgress, _feedback);
}
