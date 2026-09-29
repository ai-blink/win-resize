using WindowResizer.Core.Hotkeys;
using WindowResizer.Core.Profiles;

namespace WindowResizer.Core.Tests;

/// <summary>
/// 단축키 계획(D-026): 어떤 프로필의 어떤 세트가 등록 대상이 되는가, 그리고 PyQt5 파일에서 가져오는 값.
/// 규칙은 PyQt5 <c>_sync_profile_hotkeys</c> 와 <c>application_hotkeys.json</c> 이다.
/// </summary>
[TestClass]
public sealed class HotkeyPlanTests
{
    [TestMethod]
    public void Format_is_the_inverse_of_parse_for_every_kind_of_key()
    {
        foreach (var text in new[] { "Ctrl+Alt+E", "Shift+F1", "Ctrl+Alt+Shift+Win+F24", "Alt+7", "Ctrl+Page Up", "Win+Space", "Escape" })
        {
            Assert.AreEqual(text, HotkeyCombination.Parse(text).Format(), text);
        }
    }

    [TestMethod]
    public void Format_normalises_modifier_order_and_refuses_keys_it_cannot_name()
    {
        Assert.AreEqual("Ctrl+Alt+E", HotkeyCombination.Parse("alt+ctrl+e").Format());
        Assert.IsNull(new HotkeyCombination(HotkeyModifiers.Control, 0x01).Format(), "마우스 버튼 코드는 이름이 없다");
    }

    [TestMethod]
    public void The_real_pyqt5_file_imports_as_ctrl_alt_e_enabled()
    {
        // 이 PC 의 application_hotkeys.json 그대로(modifiers 3 = Alt|Ctrl, key_code 69 = E).
        const string json = """
            {"apply_all_profiles": {"name": "x", "modifiers": 3, "key_code": 69, "action": "apply_all_profiles",
             "parameters": {}, "enabled": true, "description": "x"}}
            """;

        Assert.AreEqual(new ApplyAllHotkey(true, "Ctrl+Alt+E"), ApplyAllHotkey.FromLegacyJson(json));
    }

    [TestMethod]
    public void A_disabled_pyqt5_entry_imports_disabled_and_keeps_its_combination()
    {
        const string json = """{"apply_all_profiles": {"modifiers": 6, "key_code": 112, "enabled": false}}""";

        Assert.AreEqual(new ApplyAllHotkey(false, "Ctrl+Shift+F1"), ApplyAllHotkey.FromLegacyJson(json));
    }

    [TestMethod]
    public void Broken_or_foreign_pyqt5_files_import_nothing()
    {
        Assert.IsNull(ApplyAllHotkey.FromLegacyJson("not json"));
        Assert.IsNull(ApplyAllHotkey.FromLegacyJson("[]"));
        Assert.IsNull(ApplyAllHotkey.FromLegacyJson("{}"));
        Assert.IsNull(ApplyAllHotkey.FromLegacyJson("""{"apply_all_profiles": {"modifiers": "3", "key_code": 69}}"""), "숫자가 아닌 값");
        Assert.IsNull(ApplyAllHotkey.FromLegacyJson("""{"apply_all_profiles": {"modifiers": 3, "key_code": 1}}"""), "이름 없는 가상 키");
    }

    [TestMethod]
    public void Only_enabled_profiles_with_the_master_switch_on_are_planned()
    {
        var document = Document(
            Profile("off", enabled: false, hotkeyEnabled: true, single: "Ctrl+F1"),
            Profile("noswitch", enabled: true, hotkeyEnabled: false, single: "Ctrl+F2"),
            Profile("ok", enabled: true, hotkeyEnabled: true, single: "Ctrl+F3"));

        var plan = HotkeyPlanner.Plan(document);

        Assert.AreEqual("Ctrl+F3", plan.Bindings.Single().Text);
        Assert.AreEqual("id-ok", plan.Bindings.Single().ProfileId);
        Assert.IsEmpty(plan.Failures);
    }

    [TestMethod]
    public void A_single_combination_counts_as_one_set_and_sets_win_when_present()
    {
        var single = Profile("single", single: "Ctrl+F1", action: "release_profile");
        var sets = Profile("sets", single: "Ctrl+F2");
        sets.Profile.HotkeySets.Add(new HotkeySet { Enabled = true, Combination = "Ctrl+F5", Action = "auto_apply_toggle" });

        var plan = HotkeyPlanner.Plan(Document(single, sets));

        CollectionAssert.AreEqual(new[] { "Ctrl+F1", "Ctrl+F5" }, plan.Bindings.Select(b => b.Text).ToArray(), "세트가 있으면 단일 조합은 무시한다");
        CollectionAssert.AreEqual(new[] { HotkeyAction.ReleaseProfile, HotkeyAction.AutoApplyToggle }, plan.Bindings.Select(b => b.Action).ToArray());
    }

    [TestMethod]
    public void A_bad_set_is_reported_and_the_rest_are_still_planned()
    {
        var profile = Profile("p");
        profile.Profile.HotkeySets.Add(new HotkeySet { Enabled = true, Combination = "Ctrl+Ctrl+A", Action = "apply_profile" });
        profile.Profile.HotkeySets.Add(new HotkeySet { Enabled = true, Combination = "Ctrl+F2", Action = "explode" });
        profile.Profile.HotkeySets.Add(new HotkeySet { Enabled = false, Combination = "Ctrl+F3", Action = "apply_profile" });
        profile.Profile.HotkeySets.Add(new HotkeySet { Enabled = true, Combination = "Ctrl+F4", Action = "always_on_top_toggle" });

        var plan = HotkeyPlanner.Plan(Document(profile));

        Assert.AreEqual("Ctrl+F4", plan.Bindings.Single().Text, "꺼진 세트는 조용히 건너뛴다");
        CollectionAssert.AreEqual(
            new[] { HotkeyFailureReason.InvalidCombination, HotkeyFailureReason.UnknownAction },
            plan.Failures.Select(f => f.Reason).ToArray());
    }

    [TestMethod]
    public void The_same_combination_twice_is_a_duplicate_across_profiles_regardless_of_spelling()
    {
        var plan = HotkeyPlanner.Plan(Document(
            Profile("a", single: "Ctrl+Alt+E"),
            Profile("b", single: "alt+ctrl+e")));

        Assert.AreEqual("id-a", plan.Bindings.Single().ProfileId);
        var failure = plan.Failures.Single();
        Assert.AreEqual(HotkeyFailureReason.Duplicate, failure.Reason);
        Assert.AreEqual("id-b", failure.ProfileId);
    }

    [TestMethod]
    public void Action_keys_round_trip_and_the_apply_all_action_is_not_a_profile_choice()
    {
        foreach (var action in HotkeyActions.ProfileActions)
        {
            Assert.IsTrue(HotkeyActions.TryParseProfileAction(HotkeyActions.ToKey(action), out var parsed));
            Assert.AreEqual(action, parsed);
        }
        Assert.IsFalse(HotkeyActions.TryParseProfileAction("apply_all_profiles", out _));
        Assert.IsFalse(HotkeyActions.TryParseProfileAction(null, out _));
    }

    private static ProfileDocument Document(params (string Id, Profile Profile)[] profiles)
    {
        var document = new ProfileDocument();
        foreach (var (id, profile) in profiles) document.Profiles.Add(new(id, profile));
        return document;
    }

    private static (string Id, Profile Profile) Profile(
        string name, bool enabled = true, bool hotkeyEnabled = true, string single = "", string action = "apply_profile") =>
        ("id-" + name, new Profile
        {
            Name = name,
            Enabled = enabled,
            HotkeyEnabled = hotkeyEnabled,
            HotkeyCombination = single,
            HotkeyAction = action,
        });
}
