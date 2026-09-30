using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using WindowResizer.Core.Profiles;

namespace WindowResizer.App.Overlay;

/// <summary>
/// 오버레이 버튼의 그림(모양, 색, 글자, 드웰 게이지). 실제 버튼 창(<see cref="OverlayButtonWindow"/>)과 버튼 속성 창의
/// 미리보기가 <b>같은 코드</b>로 그린다 - 미리보기가 실제와 다르게 보이지 않게(D-033). 크기는 스타일의 폭과 높이이고,
/// 배율은 이 컨트롤이 정하지 않는다(놓인 곳이 정한다).
/// </summary>
public partial class OverlayButtonFace : UserControl
{
    private static readonly Color SuccessBackground = Color.FromArgb(235, 38, 128, 74);
    private static readonly Color SuccessBorder = Color.FromRgb(120, 220, 160);
    private static readonly Color FailureBackground = Color.FromArgb(235, 150, 48, 48);
    private static readonly Color FailureBorder = Color.FromRgb(230, 130, 130);

    public OverlayButtonFace()
    {
        InitializeComponent();
    }

    // --- 그리기 (PyQt5 paint_overlay_face / paint_dwell_gauge) --------------------------------

    /// <param name="label">스타일의 글자를 비웠을 때 보이는 이름.</param>
    /// <param name="progress">드웰 진행률 0-1.</param>
    /// <param name="feedback">null 평소, true 성공, false 실패.</param>
    public void Draw(OverlayStyle style, string label, bool hovered, double progress, bool? feedback)
    {
        Width = Math.Max(1, style.Width);
        Height = Math.Max(1, style.Height);
        var w = Math.Max(1, style.Width);
        var h = Math.Max(1, style.Height);
        var inset = Math.Max(1.0, style.BorderWidth);
        var rect = new Rect(inset, inset, Math.Max(1, w - 2 * inset), Math.Max(1, h - 2 * inset));
        var shape = ShapeGeometry(rect, style.Shape);

        var (background, border, text) = Colors(style, hovered, feedback);
        Face.Data = shape;
        Face.Fill = new SolidColorBrush(background);
        Face.Stroke = style.BorderWidth > 0 ? new SolidColorBrush(border) : null;
        Face.StrokeThickness = style.BorderWidth;

        GaugeLayer.Clip = shape;
        var gaugeColor = ParseColor(style.GaugeColor, OverlayStyle.DefaultGauge);
        var gauge = progress <= 0 ? "none" : style.Gauge;

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
        var perimeter = Perimeter(rect, style.Shape) / OutlineGauge.StrokeThickness;
        OutlineGauge.StrokeDashArray = new DoubleCollection { perimeter * progress, perimeter * 2 };

        Label.Text = style.ResolvedLabel(label);
        Label.Foreground = new SolidColorBrush(text);
        var textInset = style.Shape == "circle" ? rect.Width * 0.18 : 12.0;
        Label.MaxWidth = Math.Max(10, rect.Width - 2 * textInset);
    }

    private static (Color Background, Color Border, Color Text) Colors(OverlayStyle style, bool hovered, bool? feedback)
    {
        if (feedback == true) return (SuccessBackground, SuccessBorder, System.Windows.Media.Colors.White);
        if (feedback == false) return (FailureBackground, FailureBorder, System.Windows.Media.Colors.White);

        var background = ParseColor(style.BackgroundColor, OverlayStyle.DefaultBackground);
        if (hovered) background = Lighter(background, 1.35);
        background.A = 235;
        return (background, ParseColor(style.BorderColor, OverlayStyle.DefaultBorder), ParseColor(style.TextColor, OverlayStyle.DefaultText));
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
