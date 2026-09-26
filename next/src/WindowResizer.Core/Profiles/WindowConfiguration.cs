using System.Text.Json.Serialization;

namespace WindowResizer.Core.Profiles;

/// <summary>
/// 창 하나의 위치와 크기.
///
/// 좌표 단위 계약: <see cref="X"/>, <see cref="Y"/>, <see cref="Width"/>, <see cref="Height"/> 는
/// <b>Win32 물리 픽셀, 가상 데스크톱 좌표</b>다. <c>GetWindowRect</c> 가 per-monitor DPI 인식
/// 프로세스에 돌려주는 값 그대로이며, 보조 모니터가 왼쪽/위에 있으면 음수가 된다.
/// WPF 의 장치 독립 픽셀(DIP)로 저장하면 안 된다 - 혼합 DPI 환경에서 창이 엉뚱한 곳으로 간다.
/// PyQt5 앱도 같은 단위로 저장한다(<c>main_window.py</c> 의 native_geometry_to_qt_geometry 참조).
/// </summary>
public sealed class WindowConfiguration
{
    [JsonPropertyName("x")] public int X { get; set; }
    [JsonPropertyName("y")] public int Y { get; set; }
    [JsonPropertyName("width")] public int Width { get; set; }
    [JsonPropertyName("height")] public int Height { get; set; }
    [JsonPropertyName("is_maximized")] public bool IsMaximized { get; set; }
    [JsonPropertyName("is_minimized")] public bool IsMinimized { get; set; }
    [JsonPropertyName("monitor_index")] public int MonitorIndex { get; set; }
    [JsonPropertyName("z_order")] public int ZOrder { get; set; }
    [JsonPropertyName("opacity")] public double Opacity { get; set; }
    [JsonPropertyName("always_on_top")] public bool AlwaysOnTop { get; set; }

    /// <summary>Python <c>WindowConfiguration.validate</c> 와 같은 규칙.</summary>
    public bool IsValid() =>
        Width > 0 && Height > 0 && Opacity >= 0 && Opacity <= 1.0 && MonitorIndex >= 0;
}
