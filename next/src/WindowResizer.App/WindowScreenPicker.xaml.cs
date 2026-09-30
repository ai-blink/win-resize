using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using WindowResizer.App.ViewModels;
using WindowResizer.Core.Windowing;
using WindowResizer.Infrastructure.Windowing;

namespace WindowResizer.App;

/// <summary>
/// 화면에서 창 고르기(D-034): 화면 캡처 도구처럼 창 위로 마우스를 옮기면 그 창에 테두리가 붙고, 클릭하면 그 창을 고른다.
/// 모니터 전체를 덮는 반투명 창이라 클릭이 아래 창으로 새지 않는다 - 고르는 것만으로 대상 창이 눌리거나 활성화되지 않는다.
/// 이 앱의 창(메인 창, 속성 창, 버튼)과 최소화된 창은 고를 수 없다. Esc 나 오른쪽 클릭이 취소다.
/// </summary>
public partial class WindowScreenPicker : Window
{
    private readonly IReadOnlyList<WindowRow> _candidates;
    private readonly uint _ownProcessId = (uint)Environment.ProcessId;
    private readonly Func<string, string> _text;

    public WindowScreenPicker(IReadOnlyList<WindowRow> candidates, Func<string, string> text)
    {
        _candidates = candidates;
        _text = text;
        InitializeComponent();
        HelpText.Text = text("ScreenPicker.Help");

        SourceInitialized += (_, _) => Cover();
        Loaded += (_, _) => { Activate(); Focus(); };
        MouseMove += (_, e) =>
        {
            var p = PointToScreen(e.GetPosition(this));
            Highlight(HitTest((int)Math.Round(p.X), (int)Math.Round(p.Y)));
        };
        MouseLeftButtonUp += (_, e) =>
        {
            var p = PointToScreen(e.GetPosition(this));
            Selected = HitTest((int)Math.Round(p.X), (int)Math.Round(p.Y));
            if (Selected is not null) DialogResult = true;
        };
        MouseRightButtonUp += (_, _) => DialogResult = false;
        // Esc 는 눌렀다 뗄 때 취소한다. 누르는 순간 닫으면 같은 Esc 가 곧바로 뒤의 속성 창에 닿아 그 창의 취소 버튼(IsCancel)까지
        // 눌러 버린다(라이브로 확인). 누르는 동안(KeyDown)은 이 창이 삼킨다.
        KeyDown += (_, e) => { if (e.Key == Key.Escape) e.Handled = true; };
        KeyUp += (_, e) => { if (e.Key == Key.Escape) { e.Handled = true; DialogResult = false; } };
    }

    /// <summary>고른 창. 취소했거나 아직 고르지 않았으면 null.</summary>
    public WindowRow? Selected { get; private set; }

    /// <summary>지금 테두리가 붙은 창.</summary>
    public WindowRow? Highlighted { get; private set; }

    /// <summary>모든 모니터를 덮는다. 좌표는 물리 픽셀이다 - WPF 의 DIP 로 정하면 배율이 다른 모니터에서 어긋난다.</summary>
    private void Cover()
    {
        var windows = new Win32Windows();
        var monitors = windows.EnumerateMonitors();
        if (monitors.Count == 0) return;

        var left = monitors.Min(m => m.Bounds.X);
        var top = monitors.Min(m => m.Bounds.Y);
        var right = monitors.Max(m => m.Bounds.X + m.Bounds.Width);
        var bottom = monitors.Max(m => m.Bounds.Y + m.Bounds.Height);
        windows.Move(new WindowInteropHelper(this).Handle, new PixelRect(left, top, right - left, bottom - top));
    }

    /// <summary>화면 좌표(물리 픽셀) 아래에서 제일 위에 보이는 고를 수 있는 창.</summary>
    public WindowRow? HitTest(int x, int y) =>
        WindowHitTest.TopmostAt(_candidates, w => w.Rect, w => w.ProcessId == _ownProcessId || w.IsMinimized, x, y);

    /// <summary>창에 테두리와 이름·크기 안내를 붙인다. null 이면 치운다.</summary>
    public void Highlight(WindowRow? row)
    {
        if (Equals(row, Highlighted)) return;
        Highlighted = row;
        if (row is null)
        {
            Frame.Visibility = Visibility.Collapsed;
            Tip.Visibility = Visibility.Collapsed;
            return;
        }

        var r = row.Rect;
        var topLeft = PointFromScreen(new Point(r.X, r.Y));
        var bottomRight = PointFromScreen(new Point(r.X + r.Width, r.Y + r.Height));
        Canvas.SetLeft(Frame, topLeft.X);
        Canvas.SetTop(Frame, topLeft.Y);
        Frame.Width = Math.Max(1, bottomRight.X - topLeft.X);
        Frame.Height = Math.Max(1, bottomRight.Y - topLeft.Y);
        Frame.Visibility = Visibility.Visible;

        TipText.Text = $"{row.Info.Title}{Environment.NewLine}{r.X}, {r.Y}  ·  {r.Width} x {r.Height}"
                       + (row.IsMaximized ? "  " + _text("Status.MaximizedMark") : "");
        Canvas.SetLeft(Tip, topLeft.X + 12);
        Canvas.SetTop(Tip, topLeft.Y + 12);
        Tip.Visibility = Visibility.Visible;
    }
}
