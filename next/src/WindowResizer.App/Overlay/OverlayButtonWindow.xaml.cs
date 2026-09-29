using System.Diagnostics;
using System.Windows;
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

    private static readonly Color SuccessBackground = Color.FromArgb(235, 38, 128, 74);
    private static readonly Color SuccessBorder = Color.FromRgb(120, 220, 160);
    private static readonly Color FailureBackground = Color.FromArgb(235, 150, 48, 48);
    private static readonly Color FailureBorder = Color.FromRgb(230, 130, 130);

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
        CloseItem.Header = text("Overlay.Button.Close");

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

    /// <summary>우클릭 "이 버튼 닫기".</summary>
    public event Action<OverlayButtonWindow>? CloseRequested;

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

    private void OnCloseClicked(object sender, RoutedEventArgs e) => CloseRequested?.Invoke(this);

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

    // --- 그리기 (PyQt5 paint_overlay_face / paint_dwell_gauge) --------------------------------

    private void Render()
    {
        var w = Math.Max(1, _style.Width);
        var h = Math.Max(1, _style.Height);
        var inset = Math.Max(1.0, _style.BorderWidth);
        var rect = new Rect(inset, inset, Math.Max(1, w - 2 * inset), Math.Max(1, h - 2 * inset));
        var shape = ShapeGeometry(rect, _style.Shape);

        var (background, border, text) = Colors();
        Face.Data = shape;
        Face.Fill = new SolidColorBrush(background);
        Face.Stroke = _style.BorderWidth > 0 ? new SolidColorBrush(border) : null;
        Face.StrokeThickness = _style.BorderWidth;

        GaugeLayer.Clip = shape;
        var progress = DwellProgress;
        var gaugeColor = ParseColor(_style.GaugeColor, OverlayStyle.DefaultGauge);
        var gauge = progress <= 0 ? "none" : _style.Gauge;

        FillGauge.Width = gauge == "fill" ? rect.Width * progress + inset : 0;
        FillGauge.Fill = new SolidColorBrush(Color.FromArgb(110, gaugeColor.R, gaugeColor.G, gaugeColor.B));

        BarGauge.Width = gauge == "bar" ? rect.Width * progress + inset : 0;
        BarGauge.Height = Math.Clamp(rect.Height * 0.12, 3.0, 8.0);
        BarGauge.Margin = new Thickness(0, 0, 0, inset);
        BarGauge.Fill = new SolidColorBrush(gaugeColor);

        // 테두리를 따라 도는 선: 외곽선을 진행률만큼만 긋는다(대시 하나 + 긴 공백).
        OutlineGauge.Data = shape;
        OutlineGauge.Stroke = gauge == "outline" ? new SolidColorBrush(gaugeColor) : null;
        OutlineGauge.StrokeThickness = 3.0;
        var perimeter = Perimeter(rect, _style.Shape) / OutlineGauge.StrokeThickness;
        OutlineGauge.StrokeDashArray = new DoubleCollection { perimeter * progress, perimeter * 2 };

        Label.Text = _style.ResolvedLabel(_profileName);
        Label.Foreground = new SolidColorBrush(text);
        var textInset = _style.Shape == "circle" ? rect.Width * 0.18 : 12.0;
        Label.MaxWidth = Math.Max(10, rect.Width - 2 * textInset);
    }

    private (Color Background, Color Border, Color Text) Colors()
    {
        if (_feedback == true) return (SuccessBackground, SuccessBorder, System.Windows.Media.Colors.White);
        if (_feedback == false) return (FailureBackground, FailureBorder, System.Windows.Media.Colors.White);

        var background = ParseColor(_style.BackgroundColor, OverlayStyle.DefaultBackground);
        if (_gesture.Hovered) background = Lighter(background, 1.35);
        background.A = 235;
        return (background, ParseColor(_style.BorderColor, OverlayStyle.DefaultBorder), ParseColor(_style.TextColor, OverlayStyle.DefaultText));
    }

    private static Geometry ShapeGeometry(Rect rect, string shape) => shape switch
    {
        "circle" => new EllipseGeometry(new Point(rect.X + rect.Width / 2, rect.Y + rect.Height / 2),
            Math.Min(rect.Width, rect.Height) / 2, Math.Min(rect.Width, rect.Height) / 2),
        "rectangle" => new RectangleGeometry(rect),
        "rounded" => new RectangleGeometry(rect, 10, 10),
        _ => new RectangleGeometry(rect, rect.Height / 2, rect.Height / 2),
    };

    private static double Perimeter(Rect rect, string shape)
    {
        if (shape == "circle") return Math.PI * Math.Min(rect.Width, rect.Height);
        var r = shape switch { "rectangle" => 0.0, "rounded" => 10.0, _ => rect.Height / 2 };
        r = Math.Min(r, Math.Min(rect.Width, rect.Height) / 2);
        return 2 * (rect.Width + rect.Height) - (8 - 2 * Math.PI) * r;
    }

    /// <summary>잘못된 색 문자열이어도 버튼은 보여야 한다(PyQt5 OVERLAY_FALLBACK_*).</summary>
    private static Color ParseColor(string value, string fallback)
    {
        try
        {
            return (Color)ColorConverter.ConvertFromString(value);
        }
        catch (Exception ex) when (ex is FormatException or NotSupportedException or NullReferenceException)
        {
            return (Color)ColorConverter.ConvertFromString(fallback);
        }
    }

    /// <summary>Qt QColor.lighter(135) 근사: HSV 명도를 곱한다.</summary>
    private static Color Lighter(Color c, double factor)
    {
        var max = Math.Max(c.R, Math.Max(c.G, c.B));
        if (max == 0) return Color.FromArgb(c.A, (byte)Math.Min(255, 255 * (factor - 1)), (byte)Math.Min(255, 255 * (factor - 1)), (byte)Math.Min(255, 255 * (factor - 1)));
        var scale = Math.Min(factor, 255.0 / max);
        return Color.FromArgb(c.A, (byte)(c.R * scale), (byte)(c.G * scale), (byte)(c.B * scale));
    }
}
