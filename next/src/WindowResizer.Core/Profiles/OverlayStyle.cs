using System.Text.Json.Serialization;

namespace WindowResizer.Core.Profiles;

/// <summary>
/// 오버레이 버튼의 생김새. 프로필마다 따로 가진다.
/// 버튼이 여러 개 떠 있을 때 생김새가 같으면 어느 것이 어느 프로필인지 구분할 수 없다.
/// 색과 모양은 장식이 아니라 식별 수단이다.
///
/// 값 보정은 Python <c>OverlayStyle.__post_init__</c> 과 같다. 읽을 때마다 <see cref="Normalize"/> 가 돈다.
/// 알 수 없는 키는 Python 과 마찬가지로 버린다.
/// </summary>
public sealed class OverlayStyle : IJsonOnDeserialized
{
    public static readonly string[] Shapes = { "pill", "rounded", "rectangle", "circle" };
    public static readonly string[] Activations = { "global", "click", "dwell" };
    public static readonly string[] Gauges = { "outline", "fill", "bar", "none" };

    public const string DefaultBackground = "#262a34";
    public const string DefaultText = "#e8ecf4";
    public const string DefaultBorder = "#6e7687";
    public const string DefaultGauge = "#78c8ff";

    [JsonPropertyName("shape")] public string Shape { get; set; } = "pill";

    /// <summary>비우면 프로필 이름을 쓴다.</summary>
    [JsonPropertyName("label")] public string Label { get; set; } = "";

    [JsonPropertyName("background_color")] public string BackgroundColor { get; set; } = DefaultBackground;
    [JsonPropertyName("text_color")] public string TextColor { get; set; } = DefaultText;
    [JsonPropertyName("border_color")] public string BorderColor { get; set; } = DefaultBorder;
    [JsonPropertyName("border_width")] public double BorderWidth { get; set; } = 1.5;
    [JsonPropertyName("width")] public int Width { get; set; } = 150;
    [JsonPropertyName("height")] public int Height { get; set; } = 46;

    /// <summary>이 프로필의 버튼을 화면에 띄울지.</summary>
    [JsonPropertyName("enabled")] public bool Enabled { get; set; }

    /// <summary><c>global</c> 은 전역 설정을 따른다는 뜻이다.</summary>
    [JsonPropertyName("activation")] public string Activation { get; set; } = "global";

    /// <summary>0 은 전역 설정을 따른다는 뜻이다. 그 외에는 200-5000 으로 맞춘다.</summary>
    [JsonPropertyName("dwell_ms")] public int DwellMs { get; set; }

    [JsonPropertyName("gauge")] public string Gauge { get; set; } = "outline";
    [JsonPropertyName("gauge_color")] public string GaugeColor { get; set; } = DefaultGauge;

    void IJsonOnDeserialized.OnDeserialized() => Normalize();

    /// <summary>범위를 벗어난 값을 되돌리고 색 표기를 소문자 한 가지로 맞춘다.</summary>
    public void Normalize()
    {
        if (!Shapes.Contains(Shape)) Shape = "pill";
        if (!Activations.Contains(Activation)) Activation = "global";
        if (!Gauges.Contains(Gauge)) Gauge = "outline";

        // 같은 색이 대소문자 때문에 다른 값으로 보이면 저장 전후 비교가 어긋난다.
        BackgroundColor = NormalizeColor(BackgroundColor);
        TextColor = NormalizeColor(TextColor);
        BorderColor = NormalizeColor(BorderColor);
        GaugeColor = NormalizeColor(GaugeColor);

        BorderWidth = Math.Clamp(BorderWidth, 0.0, 8.0);
        Width = Math.Clamp(Width, 40, 600);
        Height = Math.Clamp(Height, 28, 200);
        DwellMs = DwellMs <= 0 ? 0 : Math.Clamp(DwellMs, 200, 5000);
    }

    public string ResolvedActivation(string globalMode) => Activation == "global" ? globalMode : Activation;

    public int ResolvedDwellMs(int globalDwellMs) => DwellMs > 0 ? DwellMs : globalDwellMs;

    public string ResolvedLabel(string fallback)
    {
        var label = (Label ?? "").Trim();
        return label.Length > 0 ? label : fallback;
    }

    private static string NormalizeColor(string? value) => (value ?? "").Trim().ToLowerInvariant();
}
