using System.Text.Json;
using System.Text.Json.Serialization;

namespace WindowResizer.Core.Profiles;

/// <summary>
/// 프로필 하나에 붙는 단축키 한 벌. 편집 창은 최대 3벌을 쓴다.
/// <see cref="Action"/> 은 문자열 그대로 둔다 - 편집 창이 쓰는 값은
/// <c>apply_profile</c> / <c>release_profile</c> / <c>always_on_top_toggle</c> / <c>auto_apply_toggle</c> 이지만
/// 예전 프로필에 다른 값이 있을 수 있고, 모르는 값 때문에 프로필 전체를 버리면 안 된다.
/// </summary>
public sealed class HotkeySet
{
    [JsonPropertyName("enabled")] public bool Enabled { get; set; }
    [JsonPropertyName("combination")] public string Combination { get; set; } = "";
    [JsonPropertyName("action")] public string Action { get; set; } = "apply_profile";

    /// <summary>Python dict 에 있던 다른 키. 그대로 다시 쓴다.</summary>
    [JsonExtensionData] public Dictionary<string, JsonElement>? Extra { get; set; }
}
