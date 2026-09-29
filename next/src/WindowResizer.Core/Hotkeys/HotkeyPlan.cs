using WindowResizer.Core.Profiles;

namespace WindowResizer.Core.Hotkeys;

/// <summary>등록하려는 단축키 하나. <see cref="ProfileId"/> 는 전체 적용 단축키면 null.</summary>
public sealed record HotkeyBinding(
    HotkeyAction Action,
    HotkeyCombination Combination,
    string Text,
    string? ProfileId,
    string Label);

public enum HotkeyFailureReason
{
    /// <summary>조합을 해석하지 못했다.</summary>
    InvalidCombination,

    /// <summary>모르는 동작 이름.</summary>
    UnknownAction,

    /// <summary>같은 조합이 이미 계획에 있다(PyQt5 <c>add_hotkey</c> 의 중복 거절과 같다).</summary>
    Duplicate,

    /// <summary>OS 가 등록을 거절했다(다른 프로그램이 잡고 있음 등). <see cref="HotkeyFailure.ErrorCode"/> 에 Win32 코드.</summary>
    RegistrationFailed,
}

public sealed record HotkeyFailure(string? ProfileId, string Label, string Text, HotkeyFailureReason Reason, int ErrorCode = 0);

public sealed record HotkeyPlan(IReadOnlyList<HotkeyBinding> Bindings, IReadOnlyList<HotkeyFailure> Failures);

/// <summary>
/// 프로필 문서에서 등록할 단축키를 뽑는다. 규칙은 PyQt5 <c>_sync_profile_hotkeys</c> 와 같다:
/// 사용 중이고 <c>hotkey_enabled</c> 인 프로필만 보고, 세트가 없으면 단일 조합을 세트 하나로 본다.
/// 조합이 틀린 세트는 실패로 기록하고 나머지는 계속 계획한다.
/// </summary>
public static class HotkeyPlanner
{
    /// <summary>
    /// 프로필이 실제로 등록하려는 세트. 세트가 없고 단일 조합이 있으면 그것 하나(PyQt5 편집 창도 옛 단일 조합을
    /// 첫 세트로 읽는다). 세트가 있으면 단일 조합은 무시한다 - 등록이 그렇게 동작하기 때문이다.
    /// </summary>
    public static IReadOnlyList<HotkeySet> EffectiveSets(Profile profile)
    {
        if (profile.HotkeySets.Count > 0) return profile.HotkeySets;
        if (string.IsNullOrEmpty(profile.HotkeyCombination)) return [];
        return [new HotkeySet { Enabled = true, Combination = profile.HotkeyCombination, Action = profile.HotkeyAction }];
    }

    public static HotkeyPlan Plan(ProfileDocument document)
    {
        var bindings = new List<HotkeyBinding>();
        var failures = new List<HotkeyFailure>();
        var taken = new HashSet<HotkeyCombination>();

        foreach (var (id, profile) in document.Profiles)
        {
            if (!profile.Enabled || !profile.HotkeyEnabled) continue;

            foreach (var set in EffectiveSets(profile))
            {
                if (!set.Enabled) continue;

                var text = set.Combination.Trim();
                if (!HotkeyCombination.TryParse(text, out var combination))
                {
                    failures.Add(new HotkeyFailure(id, profile.Name, text, HotkeyFailureReason.InvalidCombination));
                    continue;
                }
                if (!HotkeyActions.TryParseProfileAction(set.Action, out var action))
                {
                    failures.Add(new HotkeyFailure(id, profile.Name, text, HotkeyFailureReason.UnknownAction));
                    continue;
                }
                if (!taken.Add(combination))
                {
                    failures.Add(new HotkeyFailure(id, profile.Name, text, HotkeyFailureReason.Duplicate));
                    continue;
                }
                bindings.Add(new HotkeyBinding(action, combination, text, id, profile.Name));
            }
        }
        return new HotkeyPlan(bindings, failures);
    }
}
