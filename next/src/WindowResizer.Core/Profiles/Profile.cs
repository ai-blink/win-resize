using System.Text.Json;
using System.Text.Json.Serialization;

namespace WindowResizer.Core.Profiles;

/// <summary>
/// 창 관리 프로필 하나. profiles.json 의 <c>profiles</c> 객체 값 하나에 대응한다.
/// 속성 순서는 Python <c>Profile</c> dataclass 필드 순서와 같다 - 쓴 파일을 사람이 비교하기 쉽게.
/// </summary>
public sealed class Profile
{
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("description")] public string Description { get; set; } = "";
    [JsonPropertyName("profile_type")] public ProfileType ProfileType { get; set; } = ProfileType.WindowConfig;
    [JsonPropertyName("window_config")] public WindowConfiguration? WindowConfig { get; set; }
    [JsonPropertyName("matching_criteria")] public MatchingCriteria? MatchingCriteria { get; set; }
    [JsonPropertyName("tags")] public List<string> Tags { get; set; } = new();

    /// <summary>Unix epoch 초(소수). Python <c>time.time()</c> 값 그대로다.</summary>
    [JsonPropertyName("created_at")] public double CreatedAt { get; set; }

    [JsonPropertyName("modified_at")] public double ModifiedAt { get; set; }
    [JsonPropertyName("applied_count")] public int AppliedCount { get; set; }
    [JsonPropertyName("last_applied_at")] public double? LastAppliedAt { get; set; }
    [JsonPropertyName("version")] public string Version { get; set; } = "1.0";

    [JsonPropertyName("auto_apply")] public bool AutoApply { get; set; }
    [JsonPropertyName("enabled")] public bool Enabled { get; set; } = true;

    [JsonPropertyName("hotkey_enabled")] public bool HotkeyEnabled { get; set; }
    [JsonPropertyName("hotkey_combination")] public string HotkeyCombination { get; set; } = "";
    [JsonPropertyName("hotkey_action")] public string HotkeyAction { get; set; } = "apply_profile";
    [JsonPropertyName("hotkey_sets")] public List<HotkeySet> HotkeySets { get; set; } = new();

    [JsonPropertyName("lock_size")] public bool LockSize { get; set; }
    [JsonPropertyName("lock_width")] public bool LockWidth { get; set; }
    [JsonPropertyName("lock_height")] public bool LockHeight { get; set; }
    [JsonPropertyName("lock_position")] public bool LockPosition { get; set; }

    [JsonPropertyName("mouse_constraint")] public bool MouseConstraint { get; set; }

    /// <summary><c>strict</c> 또는 <c>soft</c>.</summary>
    [JsonPropertyName("constraint_mode")] public string ConstraintMode { get; set; } = "strict";

    [JsonPropertyName("constraint_escape_key")] public string ConstraintEscapeKey { get; set; } = "Escape";

    [JsonPropertyName("auto_restore")] public AutoRestore? AutoRestore { get; set; }

    /// <summary>null 이면 설정한 적이 없는 것이다. 표시에는 <see cref="EffectiveOverlayStyle"/> 을 쓴다.</summary>
    [JsonPropertyName("overlay_style")] public OverlayStyle? OverlayStyle { get; set; }

    /// <summary>
    /// 이 계약이 모르는 키. 버리지 않고 그대로 다시 쓴다 - 새 PyQt5 빌드가 필드를 추가해도
    /// C# 이 한 번 저장했다고 그 값이 사라지면 안 된다.
    /// </summary>
    [JsonExtensionData] public Dictionary<string, JsonElement>? Extra { get; set; }

    public OverlayStyle EffectiveOverlayStyle => OverlayStyle ?? new OverlayStyle();

    /// <summary>사용 중이고 조건이 있을 때만 맞는다.</summary>
    public bool Matches(WindowInfo window) =>
        Enabled && MatchingCriteria is not null && MatchingCriteria.Matches(window);

    /// <summary>Python <c>apply_to_window</c> 와 같다: 적용에 성공한 창 하나마다 1 씩 센다.</summary>
    public void RecordApplied(int windows, double now)
    {
        if (windows <= 0) return;
        AppliedCount += windows;
        LastAppliedAt = now;
    }

    /// <summary>
    /// 창에서 새 프로필을 만든다(D-021). 이름은 호출자가 정한다(<see cref="ProgramName"/> + 중복 번호).
    /// 매칭은 실행 파일 경로가 있으면 경로, 없으면(상승된 프로세스 등) 프로세스 이름이다 - PyQt5 와 같다.
    /// </summary>
    public static Profile FromWindow(WindowInfo window, WindowConfiguration config, string name)
    {
        var byPath = !string.IsNullOrEmpty(window.ExecutablePath);
        return new Profile
        {
            Name = name,
            WindowConfig = config,
            MatchingCriteria = new MatchingCriteria
            {
                Strategy = byPath ? MatchingStrategy.ExecutablePath : MatchingStrategy.ProcessName,
                ExecutablePathPattern = byPath ? window.ExecutablePath : null,
                ProcessNamePattern = byPath ? null : window.ProcessName,
            },
        };
    }

    /// <summary>
    /// 기본 이름(D-021 결정 2): 창 제목이 아니라 프로그램 이름. <c>blender.exe</c> -> <c>Blender</c>.
    /// 프로세스 이름을 모르면 창 제목을 쓴다.
    /// </summary>
    public static string ProgramName(WindowInfo window)
    {
        var stem = Path.GetFileNameWithoutExtension(window.ProcessName ?? "").Trim();
        if (stem.Length == 0) return (window.Title ?? "").Trim();
        return char.ToUpperInvariant(stem[0]) + stem[1..];
    }
}
