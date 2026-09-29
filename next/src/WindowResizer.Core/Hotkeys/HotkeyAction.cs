namespace WindowResizer.Core.Hotkeys;

/// <summary>
/// 단축키가 실행하는 동작. 앞의 넷은 프로필 단축키 세트가 고르는 값이고(<c>hotkey_sets[].action</c>),
/// <see cref="ApplyAllProfiles"/> 는 프로필과 무관한 전체 적용 단축키 하나다.
/// </summary>
public enum HotkeyAction
{
    ApplyProfile,
    ReleaseProfile,
    AlwaysOnTopToggle,
    AutoApplyToggle,
    ApplyAllProfiles,
}

/// <summary>파일에 적는 동작 이름. PyQt5 <c>hotkey_sets</c> 와 같은 문자열이다.</summary>
public static class HotkeyActions
{
    /// <summary>편집 목록에 나오는 순서(PyQt5 편집 창의 콤보 순서와 같다).</summary>
    public static readonly IReadOnlyList<HotkeyAction> ProfileActions =
    [
        HotkeyAction.ApplyProfile,
        HotkeyAction.ReleaseProfile,
        HotkeyAction.AlwaysOnTopToggle,
        HotkeyAction.AutoApplyToggle,
    ];

    public static string ToKey(HotkeyAction action) => action switch
    {
        HotkeyAction.ApplyProfile => "apply_profile",
        HotkeyAction.ReleaseProfile => "release_profile",
        HotkeyAction.AlwaysOnTopToggle => "always_on_top_toggle",
        HotkeyAction.AutoApplyToggle => "auto_apply_toggle",
        _ => "apply_all_profiles",
    };

    /// <summary>프로필 세트가 쓸 수 있는 네 값만 받는다. 모르는 값은 false - 그 세트만 건너뛰고 나머지는 등록한다.</summary>
    public static bool TryParseProfileAction(string? key, out HotkeyAction action)
    {
        foreach (var candidate in ProfileActions)
        {
            if (ToKey(candidate) != key) continue;
            action = candidate;
            return true;
        }
        action = default;
        return false;
    }
}
