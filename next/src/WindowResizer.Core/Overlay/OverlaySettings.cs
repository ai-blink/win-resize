using System.Globalization;
using System.Text.Json;

namespace WindowResizer.Core.Overlay;

public enum OverlayActivation
{
    Click,
    Dwell,
}

/// <summary>화면 좌표 한 점. 단위는 프로필과 같은 Win32 물리 픽셀이다.</summary>
public readonly record struct ScreenPoint(int X, int Y);

/// <summary>
/// 오버레이 전역 설정(메뉴 지도 2.5). 독립 토글 다섯 개 + 버튼 배치 + 스위치 위치.
/// 메뉴, 트레이, 오버레이 페이지가 이 값 하나를 함께 본다.
///
/// 저장 형식은 이름-문자열 쌍이다. 해석 규칙은 PyQt5 <c>main_window.py</c> 의 읽기 코드와 같다:
/// 알 수 없는 발동 방식은 클릭, 숫자가 아닌 드웰 시간은 800ms, bool 은 <c>true/True/1</c> 만 참.
/// </summary>
public sealed class OverlaySettings
{
    public const int DefaultDwellMs = 800;
    public const int MinDwellMs = 200;
    public const int MaxDwellMs = 5000;

    public OverlayActivation Activation { get; set; } = OverlayActivation.Click;

    private int _dwellMs = DefaultDwellMs;

    /// <summary>200-5000 으로 맞춘다. PyQt5 는 아래만 막았지만 입력 창이 5.0초까지만 받았다.</summary>
    public int DwellMs
    {
        get => _dwellMs;
        set => _dwellMs = Math.Clamp(value, MinDwellMs, MaxDwellMs);
    }

    /// <summary>버튼을 감췄다. 배치와 사용 여부는 그대로다.</summary>
    public bool Hidden { get; set; }

    /// <summary>감추기 스위치를 띄운다.</summary>
    public bool ToggleVisible { get; set; }

    /// <summary>버튼과 스위치를 드래그로 옮기지 못한다.</summary>
    public bool Locked { get; set; }

    /// <summary>프로필 ID -> 버튼 왼쪽 위. 무엇을 띄울지는 프로필의 사용 여부가 정하고, 여기는 자리만 있다.</summary>
    public Dictionary<string, ScreenPoint> Layout { get; } = new();

    public ScreenPoint? TogglePosition { get; set; }

    /// <summary>
    /// 버튼들(D-032). 무엇을 띄울지는 이 목록이 정한다 - 프로필의 오버레이 사용 여부는 더 이상 버튼을 만들지 않는다.
    /// 자리(<see cref="Layout"/>)는 버튼 ID 로 저장한다.
    /// </summary>
    public List<OverlayButton> Buttons { get; } = new();

    /// <summary>프로필의 옛 버튼을 <see cref="Buttons"/> 로 한 번 복사했다. 다시 복사하지 않는다.</summary>
    public bool ButtonsMigrated { get; set; }

    /// <summary>
    /// 이름-문자열 쌍에서 읽는다. 없는 키는 기본값이다. <paramref name="includePositions"/> 가 false 면
    /// 배치와 스위치 위치를 읽지 않는다 - 좌표 단위가 다른 원본(PyQt5 논리 픽셀)에서 가져올 때 쓴다.
    /// </summary>
    public static OverlaySettings FromValues(IReadOnlyDictionary<string, string> values, bool includePositions = true)
    {
        string? Get(string key) => values.TryGetValue(key, out var v) ? v : null;

        var settings = new OverlaySettings
        {
            Activation = Get("interaction_mode") == "dwell" ? OverlayActivation.Dwell : OverlayActivation.Click,
            Hidden = IsTrue(Get("hidden")),
            ToggleVisible = IsTrue(Get("toggle_visible")),
            Locked = IsTrue(Get("locked")),
        };

        settings.DwellMs = int.TryParse(Get("dwell_ms"), NumberStyles.Integer, CultureInfo.InvariantCulture, out var ms)
            ? ms
            : DefaultDwellMs;

        settings.ButtonsMigrated = IsTrue(Get("buttons_migrated"));
        foreach (var button in ParseButtons(Get("buttons")))
            settings.Buttons.Add(button);

        if (!includePositions) return settings;

        if (int.TryParse(Get("toggle_x"), NumberStyles.Integer, CultureInfo.InvariantCulture, out var tx) &&
            int.TryParse(Get("toggle_y"), NumberStyles.Integer, CultureInfo.InvariantCulture, out var ty))
            settings.TogglePosition = new ScreenPoint(tx, ty);

        foreach (var (id, point) in ParseLayout(Get("layout")))
            settings.Layout[id] = point;

        return settings;
    }

    /// <summary>저장할 이름-문자열 쌍. 키 이름은 PyQt5 와 같다 - 두 앱의 설정을 사람이 비교하기 쉽게.</summary>
    public IReadOnlyDictionary<string, string> ToValues()
    {
        var values = new Dictionary<string, string>
        {
            ["interaction_mode"] = Activation == OverlayActivation.Dwell ? "dwell" : "click",
            ["dwell_ms"] = DwellMs.ToString(CultureInfo.InvariantCulture),
            ["hidden"] = Bool(Hidden),
            ["toggle_visible"] = Bool(ToggleVisible),
            ["locked"] = Bool(Locked),
            ["buttons_migrated"] = Bool(ButtonsMigrated),
            ["buttons"] = JsonSerializer.Serialize(Buttons),
            ["layout"] = JsonSerializer.Serialize(
                Layout.Select(p => new LayoutEntry(p.Key, p.Value.X, p.Value.Y)).ToList(), LayoutJson),
        };
        if (TogglePosition is { } t)
        {
            values["toggle_x"] = t.X.ToString(CultureInfo.InvariantCulture);
            values["toggle_y"] = t.Y.ToString(CultureInfo.InvariantCulture);
        }
        return values;
    }

    /// <summary>깨진 버튼 목록은 버린다(그 항목만, 또는 전체가 JSON 이 아니면 전체). ID 가 비었거나 겹친 항목도 버린다.</summary>
    private static IEnumerable<OverlayButton> ParseButtons(string? raw)
    {
        if (string.IsNullOrWhiteSpace(raw)) yield break;

        JsonElement root;
        try
        {
            root = JsonDocument.Parse(raw).RootElement;
        }
        catch (JsonException)
        {
            yield break;
        }
        if (root.ValueKind != JsonValueKind.Array) yield break;

        var seen = new HashSet<string>();
        foreach (var entry in root.EnumerateArray())
        {
            OverlayButton? button;
            try
            {
                button = entry.Deserialize<OverlayButton>();
            }
            catch (JsonException)
            {
                continue;
            }
            if (button is null || string.IsNullOrEmpty(button.Id) || !seen.Add(button.Id)) continue;
            yield return button;
        }
    }

    private static bool IsTrue(string? value) => value is "true" or "True" or "1";

    private static string Bool(bool value) => value ? "true" : "false";

    /// <summary>깨진 배치는 PyQt5 와 같이 버린다(그 항목만, 또는 전체가 JSON 이 아니면 전체).</summary>
    private static IEnumerable<(string Id, ScreenPoint Point)> ParseLayout(string? raw)
    {
        if (string.IsNullOrWhiteSpace(raw)) yield break;

        JsonElement root;
        try
        {
            root = JsonDocument.Parse(raw).RootElement;
        }
        catch (JsonException)
        {
            yield break;
        }
        if (root.ValueKind != JsonValueKind.Array) yield break;

        foreach (var entry in root.EnumerateArray())
        {
            if (entry.ValueKind != JsonValueKind.Object ||
                !entry.TryGetProperty("profile_id", out var id) || id.ValueKind != JsonValueKind.String ||
                // TryGetInt32 는 숫자가 아닌 값에 false 가 아니라 예외를 던진다. 종류를 먼저 본다.
                !entry.TryGetProperty("x", out var x) || x.ValueKind != JsonValueKind.Number || !x.TryGetInt32(out var xv) ||
                !entry.TryGetProperty("y", out var y) || y.ValueKind != JsonValueKind.Number || !y.TryGetInt32(out var yv))
                continue;
            yield return (id.GetString()!, new ScreenPoint(xv, yv));
        }
    }

    private sealed record LayoutEntry(
        [property: System.Text.Json.Serialization.JsonPropertyName("profile_id")] string ProfileId,
        [property: System.Text.Json.Serialization.JsonPropertyName("x")] int X,
        [property: System.Text.Json.Serialization.JsonPropertyName("y")] int Y);

    private static readonly JsonSerializerOptions LayoutJson = new();
}
