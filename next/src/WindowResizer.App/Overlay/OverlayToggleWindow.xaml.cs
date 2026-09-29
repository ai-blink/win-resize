using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using WindowResizer.Core.Overlay;
using WindowResizer.Infrastructure.Windowing;

namespace WindowResizer.App.Overlay;

/// <summary>
/// 오버레이 버튼 전체를 감췄다 꺼내는 작은 스위치(PyQt5 <c>OverlayToggleButton</c>).
///
/// 이 창은 <b>자기 자신은 절대 숨지 않는다</b> - 숨으면 다시 켤 방법이 없다. 프로필 버튼과 같이 활성화되지 않고
/// (두 겹, <see cref="Win32Windows.MakeOverlayWindow"/> + <see cref="Win32Windows.NoActivateHook"/>) 물리 픽셀로
/// 옮긴다. 끌기 문턱만 3px 로 더 낮다: 끌다 만 것이 클릭으로 읽히면 버튼이 전부 사라진다.
/// </summary>
public partial class OverlayToggleWindow : Window
{
    // Window 가 이미 Background/Foreground 를 갖고 있어 다른 이름을 쓴다.
    private static readonly Color FaceColor = (Color)ColorConverter.ConvertFromString("#262a34");
    private static readonly Color FaceColorHidden = (Color)ColorConverter.ConvertFromString("#4a3a22");
    private static readonly Color RingColor = (Color)ColorConverter.ConvertFromString("#6e7687");
    private static readonly Color IconColor = (Color)ColorConverter.ConvertFromString("#e8ecf4");

    private readonly OverlayGesture _gesture = new(OverlayGesture.SwitchDragThresholdPx);
    private readonly Func<string, string> _text;
    private bool _hidden;

    public OverlayToggleWindow(Func<string, string> text)
    {
        _text = text;
        InitializeComponent();
        Title = "WindowResizer overlay switch";
        System.Windows.Automation.AutomationProperties.SetName(this, Title);
        CloseItem.Header = text("Overlay.Toggle.Close");

        SourceInitialized += (_, _) =>
        {
            Handle = new WindowInteropHelper(this).Handle;
            IsNoActivate = Win32Windows.MakeOverlayWindow(Handle);
            HwndSource.FromHwnd(Handle)?.AddHook(Win32Windows.NoActivateHook);
        };
        MouseEnter += (_, _) => { _gesture.Enter(dwellMode: false); Render(); };
        MouseLeave += (_, _) => { _gesture.Leave(); Render(); };
        MouseLeftButtonDown += OnPress;
        MouseMove += OnMove;
        MouseLeftButtonUp += OnRelease;
        Render();
    }

    public nint Handle { get; private set; }

    /// <summary>활성화 방지 스타일이 실제로 걸렸는가.</summary>
    public bool IsNoActivate { get; private set; }

    /// <summary>클릭했다(끌지 않았다). 바꿀 값은 받는 쪽이 정한다 - 창은 설정을 모른다.</summary>
    public event Action<OverlayToggleWindow>? Clicked;

    /// <summary>드래그를 마쳤다. 인자는 새 왼쪽 위(물리 픽셀).</summary>
    public event Action<OverlayToggleWindow, ScreenPoint>? Moved;

    /// <summary>우클릭 "이 스위치 닫기".</summary>
    public event Action<OverlayToggleWindow>? CloseRequested;

    /// <summary>설정을 반영한다. 시그널은 내보내지 않는다(PyQt5 <c>set_overlays_hidden</c>).</summary>
    public void Configure(bool overlaysHidden, bool locked)
    {
        _hidden = overlaysHidden;
        _gesture.Locked = locked;
        ToolTip = _text(overlaysHidden ? "Overlay.Toggle.TipShow" : "Overlay.Toggle.TipHide")
                  + Environment.NewLine + _text(locked ? "Overlay.Button.TipLocked" : "Overlay.Button.TipDrag");
        Cursor = locked ? Cursors.Arrow : Cursors.Hand;
        Render();
    }

    private void OnPress(object sender, MouseButtonEventArgs e)
    {
        var cursor = Win32Windows.GetCursorPosition();
        if (new Win32Windows().GetRect(Handle) is not { } rect) return;
        _gesture.Press(new ScreenPoint(cursor.X, cursor.Y), new ScreenPoint(rect.X, rect.Y));
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
        var result = _gesture.Release(dwellMode: false);
        e.Handled = true;

        if (result == GestureRelease.DragEnded && new Win32Windows().GetRect(Handle) is { } rect)
            Moved?.Invoke(this, new ScreenPoint(rect.X, rect.Y));
        else if (result == GestureRelease.Click)
            Clicked?.Invoke(this);
    }

    private void OnCloseClicked(object sender, RoutedEventArgs e) => CloseRequested?.Invoke(this);

    // --- 그리기 (PyQt5 paintEvent / _paint_eye) ---------------------------------------------

    private void Render()
    {
        var face = _hidden ? FaceColorHidden : FaceColor;
        if (_gesture.Hovered) face = Lighter(face, 1.35);
        face.A = 235;
        Face.Fill = new SolidColorBrush(face);
        Face.Stroke = new SolidColorBrush(RingColor);
        Face.StrokeThickness = 1.5;

        const double left = 1.5, top = 1.5, side = 41.0;
        double cx = left + side / 2, cy = top + side / 2;
        double eyeWidth = side * 0.56, eyeHeight = side * 0.34;

        var eye = new PathFigure { StartPoint = new Point(cx - eyeWidth / 2, cy) };
        eye.Segments.Add(new QuadraticBezierSegment(new Point(cx, cy - eyeHeight), new Point(cx + eyeWidth / 2, cy), true));
        eye.Segments.Add(new QuadraticBezierSegment(new Point(cx, cy + eyeHeight), new Point(cx - eyeWidth / 2, cy), true));
        Eye.Data = new PathGeometry(new[] { eye });
        Eye.Stroke = new SolidColorBrush(IconColor);

        var pupil = side * 0.10;
        Pupil.Width = Pupil.Height = pupil * 2;
        Canvas.SetLeft(Pupil, cx - pupil);
        Canvas.SetTop(Pupil, cy - pupil);
        Pupil.Fill = new SolidColorBrush(IconColor);

        // 감춘 상태면 사선 하나.
        var offset = side * 0.30;
        (Slash.X1, Slash.Y1, Slash.X2, Slash.Y2) = (cx - offset, cy + offset, cx + offset, cy - offset);
        Slash.Stroke = new SolidColorBrush(IconColor);
        Slash.Visibility = _hidden ? Visibility.Visible : Visibility.Collapsed;
    }

    private static Color Lighter(Color c, double factor)
    {
        var max = Math.Max(c.R, Math.Max(c.G, c.B));
        var scale = max == 0 ? 1.0 : Math.Min(factor, 255.0 / max);
        return Color.FromArgb(c.A, (byte)(c.R * scale), (byte)(c.G * scale), (byte)(c.B * scale));
    }
}
