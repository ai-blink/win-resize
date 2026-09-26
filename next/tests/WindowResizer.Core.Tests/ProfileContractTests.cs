using System.Text.Json;
using WindowResizer.Core.Profiles;

namespace WindowResizer.Core.Tests;

/// <summary>
/// 프로필 계약의 순수 로직. Python 테스트에서 옮긴 것은 원래 이름을 주석에 남긴다.
/// </summary>
[TestClass]
public sealed class ProfileContractTests
{
    // tests/test_profile_preview_and_auto_apply.py
    //   test_executable_path_matching_survives_process_restart
    [TestMethod]
    public void Executable_path_matching_survives_process_restart()
    {
        var criteria = new MatchingCriteria
        {
            Strategy = MatchingStrategy.ExecutablePath,
            ExecutablePathPattern = @"C:\Apps\Target\target.exe",
        };

        Assert.IsTrue(criteria.Matches(new WindowInfo(ExecutablePath: @"C:\Apps\Target\target.exe")));
        Assert.IsFalse(criteria.Matches(new WindowInfo(ExecutablePath: @"C:\Apps\Other\target.exe")));
    }

    [TestMethod]
    public void Executable_path_is_normalized_like_python_normpath_and_normcase()
    {
        var criteria = new MatchingCriteria
        {
            Strategy = MatchingStrategy.ExecutablePath,
            ExecutablePathPattern = @"c:/apps/target/../Target/./TARGET.EXE",
        };

        Assert.IsTrue(criteria.Matches(new WindowInfo(ExecutablePath: @"C:\Apps\Target\target.exe")));

        criteria.CaseSensitive = true;
        Assert.IsFalse(criteria.Matches(new WindowInfo(ExecutablePath: @"C:\Apps\Target\target.exe")));
    }

    [TestMethod]
    public void Executable_path_never_matches_an_empty_window_path()
    {
        var criteria = new MatchingCriteria
        {
            Strategy = MatchingStrategy.ExecutablePath,
            ExecutablePathPattern = @"C:\Apps\Target\target.exe",
        };

        Assert.IsFalse(criteria.Matches(new WindowInfo()));
    }

    [TestMethod]
    public void Title_strategies_follow_the_python_rules()
    {
        var window = new WindowInfo(Title: "Untitled - Notepad");

        Assert.IsTrue(new MatchingCriteria { Strategy = MatchingStrategy.ExactTitle, WindowTitlePattern = "untitled - notepad" }.Matches(window));
        Assert.IsFalse(new MatchingCriteria { Strategy = MatchingStrategy.ExactTitle, WindowTitlePattern = "Untitled" }.Matches(window));
        Assert.IsTrue(new MatchingCriteria { Strategy = MatchingStrategy.TitleContains, WindowTitlePattern = "NOTEPAD" }.Matches(window));
        Assert.IsFalse(new MatchingCriteria { Strategy = MatchingStrategy.TitleContains, WindowTitlePattern = "NOTEPAD", CaseSensitive = true }.Matches(window));
        Assert.IsTrue(new MatchingCriteria { Strategy = MatchingStrategy.TitleRegex, WindowTitlePattern = @"^untitled\s-" }.Matches(window));
        Assert.IsTrue(new MatchingCriteria { Strategy = MatchingStrategy.TitleRegex, WindowTitlePattern = @"(?P<doc>\w+) - (?P=doc)?Notepad" }.Matches(window));
    }

    [TestMethod]
    public void Invalid_regex_is_a_mismatch_not_a_crash()
    {
        var criteria = new MatchingCriteria { Strategy = MatchingStrategy.TitleRegex, WindowTitlePattern = "([" };

        Assert.IsFalse(criteria.Matches(new WindowInfo(Title: "([")));
    }

    [TestMethod]
    public void Process_name_is_a_substring_match()
    {
        var criteria = new MatchingCriteria { Strategy = MatchingStrategy.ProcessName, ProcessNamePattern = "blender" };

        Assert.IsTrue(criteria.Matches(new WindowInfo(ProcessName: "Blender.exe")));
        Assert.IsFalse(criteria.Matches(new WindowInfo(ProcessName: "notepad.exe")));
    }

    [TestMethod]
    public void Combined_requires_every_filled_criterion_and_at_least_one()
    {
        var criteria = new MatchingCriteria
        {
            Strategy = MatchingStrategy.Combined,
            WindowTitlePattern = "Blender",
            WindowClassPattern = "GHOST",
        };

        Assert.IsTrue(criteria.Matches(new WindowInfo(Title: "Blender 5.2", ClassName: "GHOST_WindowClass")));
        Assert.IsFalse(criteria.Matches(new WindowInfo(Title: "Blender 5.2", ClassName: "Other")));
        Assert.IsFalse(new MatchingCriteria { Strategy = MatchingStrategy.Combined }.Matches(new WindowInfo(Title: "x")));
    }

    [TestMethod]
    public void Smart_strategy_never_matches()
    {
        var criteria = new MatchingCriteria { Strategy = MatchingStrategy.Smart, WindowTitlePattern = "x" };

        Assert.IsFalse(criteria.Matches(new WindowInfo(Title: "x")));
    }

    [TestMethod]
    public void Disabled_profile_or_profile_without_criteria_never_matches()
    {
        var criteria = new MatchingCriteria { Strategy = MatchingStrategy.TitleContains, WindowTitlePattern = "x" };
        var window = new WindowInfo(Title: "x");

        Assert.IsTrue(new Profile { Name = "a", MatchingCriteria = criteria }.Matches(window));
        Assert.IsFalse(new Profile { Name = "a", MatchingCriteria = criteria, Enabled = false }.Matches(window));
        Assert.IsFalse(new Profile { Name = "a" }.Matches(window));
    }

    // tests/test_overlay_style.py OverlayStyleDataTests
    [TestMethod]
    public void Overlay_style_values_are_corrected_like_python()
    {
        var style = Deserialize<OverlayStyle>(
            """{"shape":"삼각형","activation":"눈짓","gauge":"반짝임","width":9999,"height":1,"border_width":99.0,"dwell_ms":50,"background_color":" #AA3344 ","잡음":1}""");

        Assert.AreEqual("pill", style.Shape);
        Assert.AreEqual("global", style.Activation);
        Assert.AreEqual("outline", style.Gauge);
        Assert.AreEqual(600, style.Width);
        Assert.AreEqual(28, style.Height);
        Assert.AreEqual(8.0, style.BorderWidth);
        Assert.AreEqual(200, style.DwellMs);
        Assert.AreEqual("#aa3344", style.BackgroundColor);

        Assert.AreEqual(5000, Deserialize<OverlayStyle>("""{"dwell_ms":99999}""").DwellMs);
        Assert.AreEqual(0, Deserialize<OverlayStyle>("""{"dwell_ms":0}""").DwellMs);
    }

    [TestMethod]
    public void Overlay_label_falls_back_to_profile_name()
    {
        Assert.AreEqual("블렌더", new OverlayStyle { Label = "" }.ResolvedLabel("블렌더"));
        Assert.AreEqual("블렌더", new OverlayStyle { Label = "  " }.ResolvedLabel("블렌더"));
        Assert.AreEqual("B", new OverlayStyle { Label = "B" }.ResolvedLabel("블렌더"));
    }

    [TestMethod]
    public void Profile_without_overlay_style_gets_default_for_display()
    {
        var profile = new Profile { Name = "옛 프로필" };

        Assert.IsNull(profile.OverlayStyle);
        Assert.AreEqual("pill", profile.EffectiveOverlayStyle.Shape);
    }

    [TestMethod]
    public void Auto_restore_does_not_invent_keys_the_file_did_not_have()
    {
        var restore = Deserialize<AutoRestore>("""{"enabled":true,"custom_key":7}""");

        var written = JsonSerializer.Serialize(restore, ProfileJson.Options);
        using var parsed = JsonDocument.Parse(written);
        var keys = parsed.RootElement.EnumerateObject().Select(p => p.Name).ToArray();

        CollectionAssert.AreEquivalent(new[] { "enabled", "custom_key" }, keys);
        Assert.AreEqual(50, restore.EffectiveMaxAttempts);
        Assert.AreEqual(2.0, restore.EffectivePollingInterval);
    }

    [TestMethod]
    public void Non_positive_max_attempts_means_unlimited()
    {
        Assert.AreEqual(-1, new AutoRestore { MaxAttempts = -1 }.EffectiveMaxAttempts);
        Assert.AreEqual(-1, new AutoRestore { MaxAttempts = 0 }.EffectiveMaxAttempts);
        Assert.AreEqual(3, new AutoRestore { MaxAttempts = 3 }.EffectiveMaxAttempts);
    }

    [TestMethod]
    public void A_broken_profile_is_skipped_and_the_rest_still_load()
    {
        var json = """
            {
              "version": "1.0",
              "created_at": 1.5,
              "profiles": {
                "good": { "name": "좋은 프로필" },
                "bad_enum": { "name": "x", "profile_type": "nope" },
                "no_name": { "name": "  " }
              }
            }
            """;

        var result = ProfileJson.Parse(json);

        Assert.HasCount(1, result.Document.Profiles);
        Assert.AreEqual("good", result.Document.Profiles[0].Key);
        CollectionAssert.AreEquivalent(new[] { "bad_enum", "no_name" }, result.Errors.Select(e => e.ProfileId).ToArray());
    }

    [TestMethod]
    public void Parsing_is_as_strict_as_python_json()
    {
        // 파서가 던지는 실제 타입은 JsonException 의 내부 하위 타입이다.
        Assert.Throws<JsonException>(() => ProfileJson.Parse("""{"profiles": {}, }"""));
        Assert.Throws<JsonException>(() => ProfileJson.Parse("""{ /* c */ "profiles": {} }"""));
    }

    [TestMethod]
    public void Serialized_output_keeps_hangul_nulls_and_unknown_profile_keys()
    {
        var json = """
            {"version":"1.0","created_at":1786553229.4605527,"profiles":{"id1":{"name":"블렌더","overlay_style":null,"future_field":[1,2]}}}
            """;

        var written = ProfileJson.Serialize(ProfileJson.Parse(json).Document);

        StringAssert.Contains(written, "\"블렌더\"");
        StringAssert.Contains(written, "\"overlay_style\": null");
        StringAssert.Contains(written, "\"future_field\"");
        StringAssert.Contains(written, "1786553229.4605527");
        Assert.AreNotEqual('\uFEFF', written[0]);
    }

    private static T Deserialize<T>(string json) =>
        JsonSerializer.Deserialize<T>(json, ProfileJson.Options)!;
}
