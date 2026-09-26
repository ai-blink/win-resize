using System.Text.Json;
using System.Text.Json.Serialization;

namespace WindowResizer.Core.Profiles;

/// <summary>
/// 창이 프로필 위치에서 벗어나면 되돌리는 설정.
///
/// Python 쪽에서는 타입 없는 dict 이고, 빠진 키는 <b>쓰는 시점에</b> 기본값으로 채운다
/// (<c>profile_manager.py</c> 의 <c>auto_restore.get('max_attempts', 50)</c> 등).
/// 그래서 여기 필드는 전부 nullable 이고 null 이면 쓰지 않는다. C# 이 파일에 없던 키를
/// 새로 써 넣으면 Python 이 다시 읽은 dict 가 원본과 달라진다. 실제 값은 Effective* 로 읽는다.
/// </summary>
public sealed class AutoRestore
{
    private const JsonIgnoreCondition SkipNull = JsonIgnoreCondition.WhenWritingNull;

    [JsonPropertyName("enabled"), JsonIgnore(Condition = SkipNull)] public bool? Enabled { get; set; }
    [JsonPropertyName("method"), JsonIgnore(Condition = SkipNull)] public string? Method { get; set; }
    [JsonPropertyName("polling_interval"), JsonIgnore(Condition = SkipNull)] public double? PollingInterval { get; set; }
    [JsonPropertyName("quick_response"), JsonIgnore(Condition = SkipNull)] public bool? QuickResponse { get; set; }
    [JsonPropertyName("tolerance"), JsonIgnore(Condition = SkipNull)] public int? Tolerance { get; set; }
    [JsonPropertyName("restore_on_focus"), JsonIgnore(Condition = SkipNull)] public bool? RestoreOnFocus { get; set; }
    [JsonPropertyName("restore_on_resize"), JsonIgnore(Condition = SkipNull)] public bool? RestoreOnResize { get; set; }
    [JsonPropertyName("restore_on_move"), JsonIgnore(Condition = SkipNull)] public bool? RestoreOnMove { get; set; }
    [JsonPropertyName("pause_when_inactive"), JsonIgnore(Condition = SkipNull)] public bool? PauseWhenInactive { get; set; }
    [JsonPropertyName("max_attempts"), JsonIgnore(Condition = SkipNull)] public int? MaxAttempts { get; set; }

    /// <summary>Python dict 에 있던 다른 키. 그대로 다시 쓴다.</summary>
    [JsonExtensionData] public Dictionary<string, JsonElement>? Extra { get; set; }

    public bool EffectiveEnabled => Enabled ?? false;
    public string EffectiveMethod => Method ?? "hybrid";
    public double EffectivePollingInterval => PollingInterval ?? 2.0;
    public int EffectiveTolerance => Tolerance ?? 5;
    public bool EffectiveRestoreOnFocus => RestoreOnFocus ?? true;
    public bool EffectiveRestoreOnResize => RestoreOnResize ?? true;
    public bool EffectiveRestoreOnMove => RestoreOnMove ?? true;
    public bool EffectivePauseWhenInactive => PauseWhenInactive ?? false;

    /// <summary>0 이하는 무제한(-1)이다. 키가 없으면 50.</summary>
    public int EffectiveMaxAttempts => (MaxAttempts ?? 50) is var n && n > 0 ? n : -1;
}
